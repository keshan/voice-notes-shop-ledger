from __future__ import annotations

from pathlib import Path

import modal


APP_NAME = "voice-notes-shop-ledger"
MODEL_DIR = "/models"
DEFAULT_MODEL_FILE = "model.gguf"

app = modal.App(APP_NAME)
volume = modal.Volume.from_name("voice-notes-shop-ledger-models", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("build-essential", "cmake", "git", "libsndfile1")
    .pip_install(
        "fastapi[standard]>=0.115,<0.116",
        "gradio>=5.5,<6",
        "huggingface-hub>=0.36,<1",
        "llama-cpp-python>=0.3.16,<0.4",
        "pandas>=2.2,<3",
        "pydantic>=2.9,<3",
        "faster-whisper>=1.1,<2",
    )
    .add_local_dir("shop_ledger", remote_path="/root/shop_ledger")
    .env(
        {
            "PYTHONPATH": "/root",
            "LEDGER_MODEL_MODE": "llama",
            "LLAMA_GGUF_PATH": f"{MODEL_DIR}/{DEFAULT_MODEL_FILE}",
            "WHISPER_MODEL_SIZE": "tiny",
        }
    )
)


@app.function(image=image, volumes={MODEL_DIR: volume}, timeout=1800)
def download_model(repo_id: str, filename: str = DEFAULT_MODEL_FILE) -> str:
    """Download a GGUF model from Hugging Face into a persistent Modal volume."""
    from huggingface_hub import hf_hub_download

    target_path = Path(MODEL_DIR) / DEFAULT_MODEL_FILE
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False,
    )
    source = Path(downloaded_path)
    if source != target_path:
        target_path.write_bytes(source.read_bytes())
    volume.commit()
    return f"Downloaded {repo_id}/{filename} to {target_path}"


@app.cls(
    image=image,
    volumes={MODEL_DIR: volume},
    cpu=8,
    memory=32768,
    timeout=600,
)
class LedgerAgent:
    @modal.enter()
    def load(self) -> None:
        from shop_ledger.processor import LedgerProcessor

        volume.reload()
        self.processor = LedgerProcessor.from_env()

    @modal.method()
    def process(self, note: str, currency: str = "LKR") -> dict:
        result = self.processor.process(note, currency=currency)
        return result.model_dump(mode="json")


web_image = image.add_local_file("app.py", remote_path="/root/app.py")


@app.function(image=web_image, max_containers=1, timeout=600)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI
    from gradio.routes import mount_gradio_app
    from shop_ledger.ui import build_demo

    web_app = FastAPI(title="Voice Notes to Shop Ledger")

    def process_remote(note: str, currency: str) -> dict:
        return LedgerAgent().process.remote(note, currency)

    demo = build_demo(process_fn=process_remote)
    return mount_gradio_app(app=web_app, blocks=demo, path="/")


@app.local_entrypoint()
def main(repo_id: str = "", filename: str = DEFAULT_MODEL_FILE) -> None:
    if repo_id:
        print(download_model.remote(repo_id, filename))
    else:
        print("No repo_id supplied. Deploying will use heuristic fallback until a GGUF is downloaded.")
