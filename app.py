import os

from shop_ledger.ui import build_demo


if __name__ == "__main__":
    demo = build_demo()
    port = int(os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT") or "8051")
    demo.launch(server_port=port)
