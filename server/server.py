from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule
import requests
import httpx
import uuid
import os
from dotenv import load_dotenv
import tempfile
import json

load_dotenv()
app = FastAPI()


def upload_track(file_path: str, file_name: str, uid: str):
    client = Minio(
        os.getenv("MINIO_URL"),
        access_key=os.getenv("ACCESS_KEY"),
        secret_key=os.getenv("SECRET_KEY"),
        secure=False,
    )

    source_file = file_path
    bucket_name = "songs"
    destination_file = f"{uid}/{file_name}"

    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name, object_lock=True)
        print("Created bucket", bucket_name)
    else:
        print("Bucket", bucket_name, "already exists")

    config = LifecycleConfig(
        [
            Rule(
                ENABLED,
                rule_filter=Filter(prefix=""),
                rule_id="expire_songs",
                expiration=Expiration(days=1),
            ),
        ],
    )
    client.set_bucket_lifecycle(bucket_name, config)

    client.fput_object(
        bucket_name,
        destination_file,
        source_file,
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
        with tempfile.TemporaryDirectory(dir="/tmp/") as tmp_dir:
            tmp_file = tmp_dir + "/" + file.filename
            with open(tmp_file, "wb") as f:
                f.write(file.file.read())
            upload_track(tmp_file, file.filename, uid)

        data = {
            "file_name": file.filename,
            "uid": uid,
            "separate": separate,
            "track": track,
        }

        async def stream_response():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", os.getenv("LAMBDA_URL"), params=data, timeout=600
                ) as response:
                    async for chunk in response.aiter_text():
                        if "seconds" in chunk:
                            print(f"Received chunk: {chunk}")
                            yield chunk
                        try:
                            j = json.loads(chunk)
                            print(j)
                            yield json.dumps(j)
                        except:
                            pass

        return StreamingResponse(
            stream_response(),
            media_type="text/plain",
        )
    else:
        return {"error": "Invalid file format. Please upload an MP3 file."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
