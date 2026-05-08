import os

os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_mkldnn", "0")

def main() -> None:
    import paddle
    from paddleocr import PaddleOCR

    print(f"paddle={paddle.__version__}")
    print(f"paddleocr={PaddleOCR.__module__}")


if __name__ == "__main__":
    main()