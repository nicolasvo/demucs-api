from fastapi import FastAPI, File, UploadFile, Form
from minio import Minio
from minio.retention import Retention
from minio.commonconfig import GOVERNANCE

import uuid
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import tempfile

load_dotenv()
app = FastAPI()

# TODO: default remove voice from song


def upload_minio(file_path: str, file_name: str, uid: str):
    client = Minio(
        os.getenv("ENDPOINT_URL"),
        access_key=os.getenv("ACCESS_KEY"),
        secret_key=os.getenv("SECRET_KEY"),
        secure=False,
    )

    # The file to upload, change this path if needed
    source_file = file_path

    # The destination bucket and filename on the MinIO server
    bucket_name = "songs"
    # destination_file = file_name
    destination_file = f"{uid}/{file_name}"

    # Make the bucket if it doesn't exist.
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        print("Created bucket", bucket_name)
    else:
        print("Bucket", bucket_name, "already exists")

    # Upload the file, renaming it in the process
    client.fput_object(
        bucket_name,
        destination_file,
        source_file,
        retention=Retention(
            GOVERNANCE,
            datetime.now(datetime.UTC) + timedelta(days=1),
        ),
    )
    print(
        source_file,
        "successfully uploaded as object",
        destination_file,
        "to bucket",
        bucket_name,
    )


@app.post("/upload/")
async def upload_mp3_file(
    file: UploadFile = File(...),
    separate: str = Form(..., regex="^(only|everything)$"),
    track: str = Form(..., regex="^(drums|bass|other|vocals)$"),
):
    if file.content_type == "audio/mpeg":
        uid = str(uuid.uuid4())
        track_name = file.filename.split(".mp3")[0]
        with tempfile.TemporaryDirectory(dir="/tmp/") as tmp_dir:
            tmp_file = tmp_dir + "/" + file.filename
            with open(tmp_file, "wb") as f:
                f.write(file.file.read())
                upload_minio(tmp_file, file.filename, uid)

        return {
            "filename": tmp_file,
            "content_type": file.content_type,
            "separate": separate,
            "part": track,
        }
    else:
        return {"error": "Invalid file format. Please upload an MP3 file."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
