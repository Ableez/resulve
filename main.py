import uvicorn

from resulve.api.app import create_app

app = create_app()


def main():
    uvicorn.run("resulve.api.app:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
