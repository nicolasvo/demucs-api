import asyncio
import json
import subprocess
from fastapi import FastAPI
import demucs.separate
from fastapi.responses import StreamingResponse
from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta


load_dotenv()
app = FastAPI()

# TODO: default remove voice from song


def upload_track(file_path: str, file_name: str, uid: str):
    client = Minio(
        os.getenv("MINIO_URL"),
        access_key=os.getenv("ACCESS_KEY"),
        secret_key=os.getenv("SECRET_KEY"),
        secure=False,
    )

    # The file to upload, change this path if needed
    source_file = file_path

    # The destination bucket and filename on the MinIO server
    bucket_name = "separated"
    # destination_file = file_name
    destination_file = f"{uid}/{file_name}"

    # Make the bucket if it doesn't exist.
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

    # Upload the file, renaming it in the process
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


def download_track(file_name: str, uid: str, destination_file: str):
    client = Minio(
        os.getenv("MINIO_URL"),
        access_key=os.getenv("ACCESS_KEY"),
        secret_key=os.getenv("SECRET_KEY"),
        secure=False,
    )

    bucket_name = "songs"
    response = client.fget_object(bucket_name, f"{uid}/{file_name}", destination_file)


def get_presigned_url(file_name: str, uid: str):
    client = Minio(
        os.getenv("MINIO_URL"),
        access_key=os.getenv("ACCESS_KEY"),
        secret_key=os.getenv("SECRET_KEY"),
        secure=False,
    )

    bucket_name = "separated"
    url = client.presigned_get_object(
        bucket_name,
        f"{uid}/{file_name}",
        expires=timedelta(hours=1),
    )

    return url


async def run_demucs(command, tmp_dir, track_name, uid):
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )

    current_line = ""
    previous_line = ""
    while True:
        char = await process.stdout.read(1)
        if not char:
            break
        try:
            char = char.decode()
            if char == "\r":  # Carriage return, update the current line
                if current_line != previous_line:
                    print(current_line)
                    yield current_line + "\n"
                    previous_line = current_line
                current_line = ""
            elif char == "\n":  # Newline, yield the current line
                print(current_line)
                yield current_line + "\n"
                current_line = ""
                previous_line = ""
            else:
                current_line += char
        except Exception as e:
            pass

    # Process is complete, prepare the final response
    await process.wait()
    output_files = os.listdir(f"{tmp_dir}/htdemucs/{track_name}")
    presigned_urls = []
    for f in output_files:
        upload_track(f"{tmp_dir}/htdemucs/{track_name}/{f}", f"{track_name}_{f}", uid)
        presigned_urls.append(
            {
                "url": get_presigned_url(f"{track_name}_{f}", uid),
                "file": f"{track_name}_{f}",
            }
        )

    final_response = {
        "tracks": presigned_urls,
        "separate": command[3] if len(command) > 3 else "everything",
        "track": track_name,
        "log_file": f"/tmp/demucs_log_{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    }
    print(f"FINAL_RESPONSE: {json.dumps(final_response)}\n")
    yield json.dumps(final_response)


@app.post("/split_track/")
async def split_track(
    file_name: str,
    uid: str,
    separate: str,
    track: str,
):
    tmp_dir = f"/tmp/{uid}"
    tmp_file = tmp_dir + "/" + file_name
    track_name = file_name.split(".mp3")[0]
    os.makedirs(tmp_dir, exist_ok=True)
    download_track(file_name, uid, tmp_file)

    if separate == "only":
        command = [
            "demucs",
            "--mp3",
            "--two-stems",
            track,
            tmp_file,
            "-o",
            f"/tmp/{uid}",
        ]
    elif separate == "everything":
        command = ["demucs", "--mp3", tmp_file, "-o", f"/tmp/{uid}"]
    else:
        return {"error": "Invalid separation option"}

    return StreamingResponse(
        run_demucs(command, tmp_dir, track_name, uid), media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("lambda:app", host="0.0.0.0", port=8000, reload=True)
