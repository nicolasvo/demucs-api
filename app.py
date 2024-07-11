from fastapi import FastAPI, File, UploadFile, Form
import demucs.separate
# from minio import Minio
# from minio.error import S3Error

import uuid
import os

app = FastAPI()

# TODO: default remove voice from song


# def upload_minio(file_path: str, file_name: str, uuid: str):

#     client = Minio(
#         os.getenv("ENDPOINT_URL"),
#         access_key=os.getenv("ACCESS_KEY"),
#         secret_key=os.getenv("SECRET_KEY"),
#         secure=False,
#     )

#     # The file to upload, change this path if needed
#     source_file = file_path

#     # The destination bucket and filename on the MinIO server
#     bucket_name = "separated"
#     destination_file = f""

#     # Make the bucket if it doesn't exist.
#     found = client.bucket_exists(bucket_name)
#     if not found:
#         client.make_bucket(bucket_name)
#         print("Created bucket", bucket_name)
#     else:
#         print("Bucket", bucket_name, "already exists")

#     # Upload the file, renaming it in the process
#     client.fput_object(
#         bucket_name,
#         destination_file,
#         source_file,
#     )
#     print(
#         source_file,
#         "successfully uploaded as object",
#         destination_file,
#         "to bucket",
#         bucket_name,
#     )


@app.post("/upload/")
async def upload_mp3_file(
    file: UploadFile = File(...),
    separate: str = Form(..., regex="^(only|everything)$"),
    track: str = Form(..., regex="^(drums|bass|other|vocals)$"),
):
    if file.content_type == "audio/mpeg":
        uid = str(uuid.uuid4())
        tmp_dir = f"/tmp/{uid}/"
        tmp_file = tmp_dir + file.filename
        path = os.path.join("/tmp", uid)
        os.mkdir(path)
        with open(tmp_file, "wb") as f:
            f.write(file.file.read())

        if separate == "only":
            demucs.separate.main(
                ["--mp3", "--two-stems", track, tmp_file, "-o", f"/tmp/{uid}"]
            )
            # /tmp/22288c4e-7184-4e54-8d1a-bcf0dd686592/htdemucs/numb
        elif separate == "everything":
            demucs.separate.main(["--mp3", tmp_file, "-o", f"/tmp/{uid}"])
            # /tmp/7190ca17-316d-468c-8f38-44ea7df37ab2/htdemucs/numb

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
