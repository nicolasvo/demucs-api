import os
import json
import httpx
import requests
import tempfile
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

load_dotenv()
TOKEN = os.getenv("TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I split audio tracks from songs. Send me a song! 🎶"
    )


async def split_track(file_path: str, separate: str, track: str):
    url = os.getenv("SERVER_URL")
    files = {"file": (os.path.basename(file_path), open(file_path, "rb"), "audio/mpeg")}
    data = {"separate": separate, "track": track}

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", url, files=files, data=data, timeout=600
        ) as response:
            async for chunk in response.aiter_text():
                yield chunk


def download_mp3(url, output_path):
    try:
        # Send a GET request to the URL
        response = requests.get(url, stream=True)
        # Check if the request was successful
        response.raise_for_status()

        # Open a local file with write-binary mode
        with open(output_path, "wb") as file:
            # Write the content of the response to the file in chunks
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        print(f"File downloaded successfully and saved as {output_path}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download the file: {e}")


async def send_progress_updates(update: Update, response):
    message = await update.message.reply_text("Starting processing...")
    async for chunk in response:
        try:
            j = json.loads(chunk)
            await message.edit_text("Audio processing complete!")
            return j
        except:
            percentage = chunk.split("|")[0].strip()
            try:
                await message.edit_text(f"Processing audio... {percentage}")
            except:
                pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.audio:
        message_id = update.message.id
        file_id = update.message.audio.file_id
        file = await context.bot.get_file(file_id)
        os.makedirs(f"/tmp/{message_id}", exist_ok=True)
        input_path = f"/tmp/{message_id}/{update.message.audio.file_name}"
        await file.download_to_drive(input_path)
        print(f"message_id = {message_id}")
        keyboard = [
            [
                InlineKeyboardButton(
                    "Separate everything (voice, melody, bass, drums)",
                    callback_data=f"everything_{message_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Separate only one track", callback_data=f"only_{message_id}"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select how to split tracks", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Send me a song 🎵")


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message_id = query.data.split("_")[-1]
    data = query.data.split("_")[0]
    song_dir = f"/tmp/{message_id}"
    song_path = song_dir + "/" + os.listdir(song_dir)[0]
    print(f"song_path = {song_path}")
    if data == "everything":
        await query.delete_message()
        await query.message.reply_text("Splitting everything")
        response = split_track(song_path, separate="everything", track="drums")
        j = await send_progress_updates(query, response)
        bot = update.get_bot()
        with tempfile.TemporaryDirectory(dir="/tmp/") as tmp_dir:
            for t in j["tracks"]:
                print(t)
                download_mp3(t["url"], tmp_dir + "/" + t["file"])
                await bot.send_audio(query.message.chat_id, tmp_dir + "/" + t["file"])
        os.remove(song_path) if os.path.exists(song_path) else None
    if data == "track":
        track = query.data.split("_")[1]
        await query.delete_message()
        await query.message.reply_text(
            f"Splitting track: {(track if track != 'other' else 'melody')}"
        )
        response = split_track(song_path, separate="only", track=track)
        j = await send_progress_updates(query, response)
        bot = update.get_bot()
        with tempfile.TemporaryDirectory(dir="/tmp/") as tmp_dir:
            for t in j["tracks"]:
                print(t)
                download_mp3(t["url"], tmp_dir + "/" + t["file"])
                await bot.send_audio(query.message.chat_id, tmp_dir + "/" + t["file"])
        os.remove(song_path) if os.path.exists(song_path) else None
    else:
        await query.delete_message()
        keyboard = [
            [
                InlineKeyboardButton(
                    "Vocals 🎙",
                    callback_data=f"track_vocals_{message_id}",
                ),
                InlineKeyboardButton(
                    "Melody 🎹",
                    callback_data=f"track_other_{message_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Bass 🎸",
                    callback_data=f"track_bass_{message_id}",
                ),
                InlineKeyboardButton(
                    "Drums 🥁",
                    callback_data=f"track_drums_{message_id}",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Select track to split", reply_markup=reply_markup
        )


def main():
    application = Application.builder().token(TOKEN).concurrent_updates(True).build()
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(MessageHandler(filters.AUDIO, handle_message))
    application.add_handler(CallbackQueryHandler(handle_choice))
    application.add_handler(
        MessageHandler(filters.COMMAND & filters.Regex(r"/start"), start)
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
