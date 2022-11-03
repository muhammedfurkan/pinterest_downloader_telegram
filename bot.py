import asyncio
import logging
import math
import os
import time
from typing import List
from urllib import request

import pymongo
import requests
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyquery import PyQuery as pq
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import DocumentAttributeVideo

logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)


APP_ID = os.environ.get("APP_ID", None)
APP_HASH = os.environ.get("APP_HASH", None)
BOT_TOKEN = os.environ.get("BOT_TOKEN", None)
TMP_DOWNLOAD_DIRECTORY = os.environ.get("TMP_DOWNLOAD_DIRECTORY", "./DOWNLOADS/")
MONGO_DB = os.environ.get("MONGO_DB", None)

bot = TelegramClient("pinterestbot", APP_ID, APP_HASH).start(bot_token=BOT_TOKEN)


loop = asyncio.get_event_loop()

msg = """
Merhaba ben Pinterest üzerinden Video ve Resim indirebilen bir botum.
`Hello, I am a bot that can download Videos and Images via Pinterest.`

Şunları yapabilirim:
`I can:`

👉 **Video indirmek için:** `/pvid pinterestURL`
👉 **To download a video:** `/pvid pinterestURL`


👉 **Resim indirebilmek için:** `/pimg pinterestURL`
👉 **To download a image:** `/pimg pinterestURL`
"""


SESSION_ADI = "pinterest"


class pinterest_db:
    def __init__(self):
        client = pymongo.MongoClient(MONGO_DB)
        db = client["Telegram"]
        self.collection = db[SESSION_ADI]

    def ara(self, sorgu: dict):
        say = self.collection.count_documents(sorgu)
        if say == 1:
            return self.collection.find_one(sorgu, {"_id": 0})
        elif say > 1:
            cursor = self.collection.find(sorgu, {"_id": 0})
            return {
                bak["uye_id"]: {"uye_nick": bak["uye_nick"], "uye_adi": bak["uye_adi"]}
                for bak in cursor
            }
        else:
            return None

    def ekle(self, uye_id, uye_nick, uye_adi):
        if not self.ara({"uye_id": {"$in": [str(uye_id), int(uye_id)]}}):
            return self.collection.insert_one(
                {
                    "uye_id": uye_id,
                    "uye_nick": uye_nick,
                    "uye_adi": uye_adi,
                }
            )
        else:
            return None

    def sil(self, uye_id):
        if not self.ara({"uye_id": {"$in": [str(uye_id), int(uye_id)]}}):
            return None

        self.collection.delete_one({"uye_id": {"$in": [str(uye_id), int(uye_id)]}})
        return True

    @property
    def kullanici_idleri(self):
        return list(self.ara({"uye_id": {"$exists": True}}).keys())


async def log_yolla(event):
    j = await event.client(GetFullUserRequest(event.chat_id))
    uye_id = j.user.id
    uye_nick = f"@{j.user.username}" if j.user.username else None
    uye_adi = f"{j.user.first_name or ''} {j.user.last_name or ''}".strip()
    komut = event.text

    # Kullanıcı Kaydet
    db = pinterest_db()
    db.ekle(uye_id, uye_nick, uye_adi)


# total number of users using the bot
@bot.on(events.NewMessage(pattern="/kul_say"))
async def say(event):
    j = await event.client(GetFullUserRequest(event.chat_id))

    db = pinterest_db()
    db.ekle(j.user.id, j.user.username, j.user.first_name)

    def KULLANICILAR():
        return db.kullanici_idleri

    await event.client.send_message(
        "By_Azade", f"ℹ️ `{len(KULLANICILAR())}` __Adet Kullanıcıya Sahipsin..__"
    )


# Command to make an announcement to users using the bot
@bot.on(events.NewMessage(pattern="/duyuru ?(.*)"))
async def duyuru(event):
    # < Başlangıç
    await log_yolla(event)

    ilk_mesaj = await event.client.send_message(
        event.chat_id, "⌛️ `Hallediyorum..`", reply_to=event.chat_id, link_preview=False
    )
    # ------------------------------------------------------------- Başlangıç >

    db = pinterest_db()

    def KULLANICILAR():
        return db.kullanici_idleri

    if not KULLANICILAR():
        await ilk_mesaj.edit("ℹ️ __Start vermiş kimse yok kanka..__")
        return

    if not event.message.reply_to:
        await ilk_mesaj.edit("⚠️ __Duyurmak için mesaj yanıtlayın..__")
        return

    basarili = 0
    hatalar = []
    mesaj_giden_kisiler = []
    get_reply_msg = await event.get_reply_message()
    for kullanici_id in KULLANICILAR():
        try:
            await event.client.send_message(
                entity=kullanici_id, message=get_reply_msg.message
            )
            mesaj_giden_kisiler.append(kullanici_id)
            basarili += 1
        except Exception as hata:
            hatalar.append(type(hata).__name__)
            db.sil(kullanici_id)

    mesaj = (
        f"⁉️ `{len(hatalar)}` __Adet Kişiye Mesaj Atamadım ve DB'den Sildim..__\n\n"
        if hatalar
        else ""
    )
    mesaj += f"📜 `{basarili}` __Adet Kullanıcıya Mesaj Attım..__"

    await ilk_mesaj.edit(mesaj)


@bot.on(events.NewMessage(pattern="/start", func=lambda e: e.is_private))
async def start(event):
    await log_yolla(event)
    j = await event.client(GetFullUserRequest(event.chat_id))
    mesaj = f"Gönderen [{j.user.first_name}](tg://user?id={event.chat_id})\nMesaj: {event.message.message}"
    await bot.send_message("By_Azade", mesaj)
    if event:
        markup = bot.build_reply_markup(
            [
                [
                    Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                    Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
                ],
                [
                    Button.url(
                        text="🔗 GitHub Repo",
                        url="https://github.com/muhammedfurkan/pinterest_downloader_telegram",
                    )
                ],
                [Button.inline(text="🤖 Diğer Botlar", data="digerbotlar")],
            ]
        )
        await bot.send_message(event.chat_id, msg, buttons=markup, link_preview=False)


@bot.on(events.NewMessage(pattern="/pvid ?(.*)", func=lambda e: e.is_private))
async def vid(event):
    await log_yolla(event)
    try:
        j = await event.client(GetFullUserRequest(event.chat_id))
        mesaj = f"Gönderen [{j.user.first_name}](tg://user?id={event.chat_id})\nMesaj: {event.message.message}"
        await bot.send_message("By_Azade", mesaj)
        markup = bot.build_reply_markup(
            [
                [
                    Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                    Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
                ],
                [Button.inline(text="🤖 Diğer Botlar", data="digerbotlar")],
            ]
        )

        url = event.pattern_match.group(1)
        if url:
            x = await event.reply("`işlem yapılıyor bekleyiniz...`")

            get_url = get_download_url(url)
            # await loop.run_in_executor(None, download_video(get_url))
            j = await loop.run_in_executor(None, download_video, get_url)
            thumb_image_path = TMP_DOWNLOAD_DIRECTORY + "thumb_image.jpg"

            if not os.path.isdir(TMP_DOWNLOAD_DIRECTORY):
                os.makedirs(TMP_DOWNLOAD_DIRECTORY)

            metadata = extractMetadata(createParser(j))
            duration = 0

            if metadata.has("duration"):
                duration = metadata.get("duration").seconds
                width = 0
                height = 0
                thumb = None

            if os.path.exists(thumb_image_path):
                thumb = thumb_image_path
            else:
                thumb = await take_screen_shot(
                    j, os.path.dirname(os.path.abspath(j)), (duration / 2)
                )
            width = 0
            height = 0
            if os.path.exists(thumb_image_path):
                metadata = extractMetadata(createParser(thumb_image_path))
                if metadata.has("width"):
                    width = metadata.get("width")
                if metadata.has("height"):
                    height = metadata.get("height")
            c_time = time.time()
            await event.client.send_file(
                event.chat_id,
                j,
                thumb=thumb,
                caption="**@Pinterestdown_Robot** tarafından indirilmiştir\n\nDownloaded by **@Pinterestdown_Robot**",
                force_document=False,
                allow_cache=False,
                reply_to=event.message.id,
                buttons=markup,
                attributes=[
                    DocumentAttributeVideo(
                        duration=duration,
                        w=width,
                        h=height,
                        round_message=False,
                        supports_streaming=True,
                    )
                ],
                progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                    progress(d, t, event, c_time, "yükleniyor...")
                ),
            )
            await event.delete()
            await x.delete()
            os.remove(TMP_DOWNLOAD_DIRECTORY + "pinterest_video.mp4")
            os.remove(thumb_image_path)
        else:
            await event.reply(
                "**bana komutla beraber link gönder.**\n\n`send me the link with the command.`"
            )
    except FileNotFoundError:
        return


@bot.on(events.NewMessage(pattern="/pimg ?(.*)", func=lambda e: e.is_private))
async def img(event):
    await log_yolla(event)
    j = await event.client(GetFullUserRequest(event.chat_id))
    mesaj = f"Gönderen [{j.user.first_name}](tg://user?id={event.chat_id})\nMesaj: {event.message.message}"
    await bot.send_message("By_Azade", mesaj)
    markup = bot.build_reply_markup(
        [
            [
                Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
            ],
            [Button.inline(text="🤖 Diğer Botlar", data="digerbotlar")],
        ]
    )
    url = event.pattern_match.group(1)
    if url:
        x = await event.reply(
            "`İşlem yapılıyor lütfen bekleyiniz...`\n\nProcessing please wait ..."
        )
        get_url = get_download_url(url)
        j = await loop.run_in_executor(None, download_video, get_url)

        if not os.path.isdir(TMP_DOWNLOAD_DIRECTORY):
            os.makedirs(TMP_DOWNLOAD_DIRECTORY)
        c_time = time.time()
        await event.client.send_file(
            event.chat_id,
            j,
            caption="**@Pinterestdown_Robot** tarafından indirilmiştir\n\nDownloaded by **@Pinterestdown_Robot**",
            force_document=False,
            allow_cache=False,
            reply_to=event.message.id,
            buttons=markup,
            progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                progress(d, t, event, c_time, "yükleniyor...")
            ),
        )
        await event.delete()
        await x.delete()
        os.remove(TMP_DOWNLOAD_DIRECTORY + "pinterest_iamge.jpg")
    else:
        await event.reply(
            "**bana komutla beraber link gönder.**\n\n`send me the link with the command.`"
        )


@bot.on(events.CallbackQuery(pattern=b"digerbotlar"))
async def digerbotlar(event):
    markup = bot.build_reply_markup(
        [
            [
                Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
            ],
            [Button.inline(text="Ana Sayfa", data="ana")],
        ]
    )
    await event.edit(
        "**Diğer Botlarımız:**\n\n"
        + "📍 [A101 Katalog Bot](t.me/A101KatalogBot)\n"
        + "📍 [Osmanlıca Bot](t.me/OsmanlicamBot)\n"
        + "📍 [Döviz Bot](t.me/DovizRobot)\n"
        + "📍 [Pinterest Video Resim İndirici Bot](t.me/A101KatalogBot)\n"
        + "📍 [Arşiv Çıkarıcı Bot](t.me/ExtractorRobot)\n"
        + "📍 [Vimeo Video İndirici Bot](t.me/vimeo_robot)\n"
        + "📍 [Tureng Bot](t.me/TurengRobot)\n"
        + "📍 [TDK Bot](t.me/TDK_ROBOT)\n"
        + "📍 [Müzik Arama Bot](t.me/muzikaramabot)\n"
        + "📍 [ÖSYM Bot](t.me/OSYMRobot)\n"
        + "📍 [Youtube Playlist İndirici Bot](t.me/PlaylistIndirRobot)\n"
        + "📍 [Drive Upload Bot](t.me/driveyuklebot)\n"
        + "📍 [GoFile Upload Bot](t.me/GofileRobot)\n"
        + "📍 [Bim Aktuel Ürünler Bot](t.me/BimAktuelBot)\n"
        + "📍 [Dosya Ara Bot](t.me/DosyaAraBot)\n"
        + "🆕 [Spotify & YouTube İndirici](t.me/YouTubeSpotifyMp3IndirBot)\n"
        + "🆕 [Streamtape Bot](t.me/StreamTapeUploaderBot)\n"
        + "🆕 [Şok Aktuel Bot](t.me/SokAktuelBot)\n",
        link_preview=False,
        buttons=markup,
    )


@bot.on(events.CallbackQuery(pattern=b"ana"))
async def ana(event):
    markup = bot.build_reply_markup(
        [
            [
                Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
            ],
            [
                Button.url(
                    text="🔗 GitHub Repo",
                    url="https://github.com/muhammedfurkan/pinterest_downloader_telegram",
                )
            ],
            [Button.inline(text="🤖 Diğer Botlar", data="digerbotlar")],
        ]
    )
    await event.edit(msg, buttons=markup, link_preview=False)


async def run_command(command: List[str]) -> (str, str):
    process = await asyncio.create_subprocess_exec(
        *command,
        # stdout must a pipe to be accessible as process.stdout
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    return t_response, e_response


async def take_screen_shot(video_file, output_directory, ttl):
    # https://stackoverflow.com/a/13891070/4723940
    out_put_file_name = output_directory + "/" + str(time.time()) + ".jpg"
    file_genertor_command = [
        "ffmpeg",
        "-ss",
        str(ttl),
        "-i",
        video_file,
        "-vframes",
        "1",
        out_put_file_name,
    ]
    t_response, e_response = await run_command(file_genertor_command)
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    logger.info(e_response)
    logger.info(t_response)
    return None


def humanbytes(size):
    """Input size in bytes,
    outputs in a human readable format"""
    # https://stackoverflow.com/a/49361727/4723940
    if not size:
        return ""
    # 2 ** 10 = 1024
    power = 2**10
    raised_to_pow = 0
    dict_power_n = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        raised_to_pow += 1
    return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "B"


def time_formatter(seconds: int) -> str:
    """Inputs time in seconds, to get beautified time,
    as string"""
    result = ""
    v_m = 0
    remainder = seconds
    r_ange_s = {"days": 24 * 60 * 60, "hours": 60**2, "minutes": 60, "seconds": 1}
    for age, divisor in r_ange_s.items():
        v_m, remainder = divmod(remainder, divisor)
        v_m = int(v_m)
        if v_m != 0:
            result += f" {v_m} {age} "
    return result


async def progress(current, total, event, start, type_of_ps):
    """Generic progress_callback for both
    upload.py and download.py"""
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        elapsed_time = round(diff)
        if elapsed_time == 0:
            return
        speed = current / diff
        time_to_completion = round((total - current) / speed)
        estimated_total_time = elapsed_time + time_to_completion
        progress_str = "[{0}{1}]\nPercent: {2}%\n".format(
            "".join(["█" for _ in range(math.floor(percentage / 5))]),
            "".join(["░" for _ in range(20 - math.floor(percentage / 5))]),
            round(percentage, 2),
        )
        tmp = progress_str + "{0} of {1}\nETA: {2}".format(
            humanbytes(current), humanbytes(total), time_formatter(estimated_total_time)
        )
        await event.edit("{}\n {}".format(type_of_ps, tmp))


# Function to get download url
def get_download_url(link):
    # Make request to website
    post_request = requests.post(
        "https://www.expertsphp.com/download.php", data={"url": link}
    )

    # Get content from post request
    request_content = post_request.content
    str_request_content = str(request_content, "utf-8")
    return pq(str_request_content)("table.table-condensed")("tbody")("td")("a").attr(
        "href"
    )


# Function to download video
def download_video(url):
    if not os.path.isdir(TMP_DOWNLOAD_DIRECTORY):
        os.makedirs(TMP_DOWNLOAD_DIRECTORY)
    video_to_download = request.urlopen(url).read()
    with open(TMP_DOWNLOAD_DIRECTORY + "pinterest_video.mp4", "wb") as video_stream:
        video_stream.write(video_to_download)
    return TMP_DOWNLOAD_DIRECTORY + "pinterest_video.mp4"


# Function to download image
def download_image(url):
    if not os.path.isdir(TMP_DOWNLOAD_DIRECTORY):
        os.makedirs(TMP_DOWNLOAD_DIRECTORY)
    image_to_download = request.urlopen(url).read()
    with open(TMP_DOWNLOAD_DIRECTORY + "pinterest_iamge.jpg", "wb") as photo_stream:
        photo_stream.write(image_to_download)
    return TMP_DOWNLOAD_DIRECTORY + "pinterest_iamge.jpg"


bot.start()
bot.run_until_disconnected()
