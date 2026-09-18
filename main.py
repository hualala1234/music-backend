import os
import re
import json
import uuid
from typing import Optional

import requests
import firebase_admin

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Header
)
from pydantic import BaseModel, Field

from firebase_admin import (
    credentials,
    firestore,
    storage,
    auth as firebase_auth
)


# ============================================================
# 1. 環境設定
# ============================================================

load_dotenv()


# ------------------------------------------------------------
# Suno
# ------------------------------------------------------------

SUNO_API_KEY = os.getenv("SUNO_API_KEY")

if not SUNO_API_KEY:
    raise RuntimeError(
        "找不到 SUNO_API_KEY，請確認 .env 是否設定"
    )

BASE_URL = "https://api.sunoapi.org"


# ------------------------------------------------------------
# Firebase
# ------------------------------------------------------------

FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH"
)

FIREBASE_STORAGE_BUCKET = os.getenv(
    "FIREBASE_STORAGE_BUCKET"
)

if not FIREBASE_SERVICE_ACCOUNT_PATH:
    raise RuntimeError(
        "找不到 FIREBASE_SERVICE_ACCOUNT_PATH"
    )

if not FIREBASE_STORAGE_BUCKET:
    raise RuntimeError(
        "找不到 FIREBASE_STORAGE_BUCKET"
    )



# ------------------------------------------------------------
# 初始化 Firebase Admin SDK
# ------------------------------------------------------------

if not firebase_admin._apps:

    cred = credentials.Certificate(
        FIREBASE_SERVICE_ACCOUNT_PATH
    )

    firebase_admin.initialize_app(
        cred,
        {
            "storageBucket":
                FIREBASE_STORAGE_BUCKET
        }
    )


# Firestore
db = firestore.client()

# Firebase Storage
bucket = storage.bucket()

print("✅ Firebase Admin SDK 初始化成功")

# ============================================================
# Firebase Authentication
# ============================================================

def get_current_uid(
    authorization: Optional[str]
) -> str:

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="缺少 Authorization Header"
        )


    if not authorization.startswith(
        "Bearer "
    ):
        raise HTTPException(
            status_code=401,
            detail="Authorization 格式錯誤"
        )


    id_token = authorization[
        len("Bearer "):
    ].strip()


    if not id_token:
        raise HTTPException(
            status_code=401,
            detail="Firebase ID Token 為空"
        )


    try:

        decoded_token = (
            firebase_auth.verify_id_token(
                id_token
            )
        )


        uid = decoded_token.get(
            "uid"
        )


        if not uid:
            raise HTTPException(
                status_code=401,
                detail="Token 中沒有 uid"
            )


        return uid


    except HTTPException:
        raise


    except Exception as e:

        print(
            "❌ Firebase Token 驗證失敗：",
            str(e)
        )


        raise HTTPException(
            status_code=401,
            detail="Firebase ID Token 無效"
        )

# ============================================================
# 2. FastAPI
# ============================================================

app = FastAPI(
    title="Lumi Music API",
    version="1.0.0"
)


# ============================================================
# 3. Suno Prompt Tag Mapping
# ============================================================

# ------------------------------------------------------------
# 3-1. moods
# ------------------------------------------------------------

MOOD_MAP = {
    "relaxing": "relaxing",
    "calm": "calm and peaceful",
    "healing": "soothing and healing",
    "comforting": "comforting and reassuring",
    "focused": "focused and unobtrusive",
    "immersive": "immersive",
    "refreshing": "refreshing and clear-minded",
    "warm": "warm and comforting",
    "ethereal": "ethereal",
    "dreamy": "dreamy",
}


# ------------------------------------------------------------
# 3-2. style
# ------------------------------------------------------------

STYLE_MAP = {
    "ambient": "ambient meditation music",
    "lofi": "gentle lo-fi meditation music",
    "piano_meditation": "peaceful piano meditation music",
    "nature_healing": "nature-inspired healing meditation music",
    "zen": "zen meditation music",
    "eastern_meditation": "eastern-inspired meditation music",
    "new_age": "new age meditation music",
    "cinematic": "cinematic ambient meditation music",
    "minimalist": "minimalist meditation music",
    "singing_bowl_meditation": "singing bowl meditation music",
}


# ------------------------------------------------------------
# 3-3. instruments
# ------------------------------------------------------------

INSTRUMENT_MAP = {
    "piano": "soft piano",
    "acoustic_guitar": "gentle acoustic guitar",
    "flute": "soft flute",
    "harp": "gentle harp",
    "strings": "soft strings",
    "singing_bowls": "singing bowls",
    "wind_chimes": "delicate wind chimes",
    "synth": "soft atmospheric synthesizer",
    "guzheng": "gentle guzheng",
    "xiao": "soft xiao flute",
}


# ------------------------------------------------------------
# 3-4. natureSound
# ------------------------------------------------------------

NATURE_SOUND_MAP = {
    "none": None,
    "rain": "gentle rain ambience",
    "ocean_waves": "soft ocean waves",
    "stream": "gentle flowing stream",
    "forest": "peaceful forest ambience",
    "birds": "soft distant birdsong",
    "rustling_leaves": "gentle wind through leaves",
    "campfire": "soft crackling campfire",
    "night_insects": "subtle nighttime insect ambience",
    "thunderstorm": "distant gentle thunder and rain",
}


# ------------------------------------------------------------
# 3-5. tempo
# ------------------------------------------------------------

TEMPO_MAP = {
    "beatless": "beatless and free-flowing",
    "very_slow": "very slow tempo",
    "slow": "slow tempo",
    "steady": "gentle steady pulse",
    "light_beat": "subtle light beat",
}


# ------------------------------------------------------------
# 3-6. scene
# ------------------------------------------------------------

SCENE_MAP = {
    "morning_forest": "peaceful early-morning forest",
    "rainy_window": "quiet rainy window scene",
    "peaceful_beach": "peaceful seaside",
    "midnight_stars": "serene midnight under the stars",
    "misty_mountains": "misty mountain atmosphere",
    "cozy_room": "warm cozy room",
    "floating_space": "weightless floating through space",
    "sunset_lakeside": "tranquil lakeside at sunset",
    "forest_cabin": "peaceful forest cabin",
    "peaceful_temple": "serene meditation temple",
}


# ------------------------------------------------------------
# 3-7. textures
# ------------------------------------------------------------

TEXTURE_MAP = {
    "soft": "soft",
    "warm": "warm-toned",
    "clear": "clear and clean",
    "deep": "deep and resonant",
    "ethereal": "airy and ethereal",
    "hazy": "hazy and diffused",
    "bright": "gently bright",
    "spacious": "spacious and expansive",
}


# ============================================================
# 4. 中文 Description Mapping
# ============================================================

MOOD_ZH_MAP = {
    "relaxing": "放鬆",
    "calm": "平靜",
    "healing": "療癒",
    "comforting": "安心",
    "focused": "專注",
    "immersive": "沉浸",
    "refreshing": "清醒",
    "warm": "溫暖",
    "ethereal": "空靈",
    "dreamy": "夢幻",
}


STYLE_ZH_MAP = {
    "ambient": "氛圍音樂",
    "lofi": "Lo-fi",
    "piano_meditation": "鋼琴冥想",
    "nature_healing": "自然療癒",
    "zen": "禪意",
    "eastern_meditation": "東方冥想",
    "new_age": "新世紀",
    "cinematic": "電影感",
    "minimalist": "極簡",
    "singing_bowl_meditation": "頌缽冥想",
}


INSTRUMENT_ZH_MAP = {
    "piano": "鋼琴",
    "acoustic_guitar": "木吉他",
    "flute": "長笛",
    "harp": "豎琴",
    "strings": "弦樂",
    "singing_bowls": "頌缽",
    "wind_chimes": "風鈴",
    "synth": "合成器",
    "guzheng": "古箏",
    "xiao": "簫",
}


NATURE_SOUND_ZH_MAP = {
    "none": "",
    "rain": "雨聲",
    "ocean_waves": "海浪",
    "stream": "溪流",
    "forest": "森林",
    "birds": "鳥鳴",
    "rustling_leaves": "風吹樹葉",
    "campfire": "營火",
    "night_insects": "夜晚蟲鳴",
    "thunderstorm": "雷雨",
}


TEMPO_ZH_MAP = {
    "beatless": "無節拍",
    "very_slow": "非常緩慢",
    "slow": "緩慢",
    "steady": "穩定律動",
    "light_beat": "輕微節拍",
}


SCENE_ZH_MAP = {
    "morning_forest": "清晨森林",
    "rainy_window": "雨天窗邊",
    "peaceful_beach": "寧靜海邊",
    "midnight_stars": "深夜星空",
    "misty_mountains": "山間雲霧",
    "cozy_room": "溫暖房間",
    "floating_space": "宇宙漂浮",
    "sunset_lakeside": "日落湖畔",
    "forest_cabin": "森林小屋",
    "peaceful_temple": "祥靜寺院",
}


TEXTURE_ZH_MAP = {
    "soft": "柔和",
    "warm": "溫暖",
    "clear": "清澈",
    "deep": "深沉",
    "ethereal": "空靈",
    "hazy": "朦朧",
    "bright": "明亮",
    "spacious": "寬廣",
}


# ============================================================
# 5. Suno Status
# ============================================================

PROCESSING_STATUSES = {
    "PENDING",
    "TEXT_SUCCESS"
}

READY_STATUSES = {
    "FIRST_SUCCESS",
    "SUCCESS"
}

FAILED_STATUSES = {
    "FAILED",
    "CREATE_TASK_FAILED",
    "GENERATE_AUDIO_FAILED",
    "CALLBACK_EXCEPTION",
    "SENSITIVE_WORD_ERROR"
}


# ============================================================
# 6. Unity 傳進來的資料格式
# ============================================================

class GenerateMusicRequest(BaseModel):

    # 01 你現在想聽什麼感覺？
    # 必選 1
    moods: list[str]

    # 02 你喜歡哪種音樂？
    style: str
    tempo: str

    # 必選 1（Array 中只能有 1 個值）
    textures: list[str]

    # 03 想加入哪些聲音？
    # 0～3
    instruments: list[str] = Field(
        default_factory=list
    )

    natureSound: str

    # 04 想在哪裡聽這首音樂？
    # 可跳過
    scene: Optional[str] = None

    # 05 自由輸入
    freeText: str = ""


# ============================================================
# 7. 共用工具
# ============================================================

def join_phrases(
    items: list[str]
) -> str:

    if len(items) == 0:
        return ""

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return (
            f"{items[0]} and {items[1]}"
        )

    return (
        ", ".join(items[:-1])
        + f", and {items[-1]}"
    )


def join_zh(
    items: list[str]
) -> str:

    if not items:
        return ""

    return "、".join(items)


def validate_keys(
    values: list[str],
    mapping: dict,
    field_name: str
):

    invalid_values = [
        value
        for value in values
        if value not in mapping
    ]

    if invalid_values:

        raise HTTPException(
            status_code=400,
            detail={
                "message":
                    f"{field_name} 包含不存在的 Tag Key",

                "invalidValues":
                    invalid_values
            }
        )


def clean_free_text(
    text: str
) -> str:

    if not text:
        return ""

    text = text.strip()

    text = re.sub(
        r"[\x00-\x1F\x7F]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# 8. 驗證使用者選擇
# ============================================================

def validate_music_request(
    request: GenerateMusicRequest
):

    # moods：Array，但只能單選 1 個
    if len(request.moods) != 1:
        raise HTTPException(
            status_code=400,
            detail="moods 只能選擇 1 個"
        )

    validate_keys(
        request.moods,
        MOOD_MAP,
        "moods"
    )


    # style
    if request.style not in STYLE_MAP:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不存在的 style Tag Key："
                f"{request.style}"
            )
        )


    # tempo
    if request.tempo not in TEMPO_MAP:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不存在的 tempo Tag Key："
                f"{request.tempo}"
            )
        )


    # textures：Array，但只能單選 1 個
    if len(request.textures) != 1:
        raise HTTPException(
            status_code=400,
            detail="textures 只能選擇 1 個"
        )

    validate_keys(
        request.textures,
        TEXTURE_MAP,
        "textures"
    )


    # instruments
    if len(request.instruments) > 3:
        raise HTTPException(
            status_code=400,
            detail="instruments 最多只能選擇 3 個"
        )

    if len(set(request.instruments)) != len(
        request.instruments
    ):
        raise HTTPException(
            status_code=400,
            detail="instruments 不可重複選擇"
        )

    validate_keys(
        request.instruments,
        INSTRUMENT_MAP,
        "instruments"
    )


    # natureSound
    if (
        request.natureSound
        not in NATURE_SOUND_MAP
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"不存在的 natureSound Tag Key："
                f"{request.natureSound}"
            )
        )


    # scene
    if (
        request.scene is not None
        and request.scene != ""
        and request.scene not in SCENE_MAP
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"不存在的 scene Tag Key："
                f"{request.scene}"
            )
        )


    # freeText
    cleaned_free_text = clean_free_text(
        request.freeText
    )

    if len(cleaned_free_text) > 100:
        raise HTTPException(
            status_code=400,
            detail=(
                "freeText 最多只能輸入 "
                "100 個字元"
            )
        )


# ============================================================
# 9. Prompt Builder
# ============================================================

def build_prompt(
    request: GenerateMusicRequest
) -> str:

    prompt_parts = []


    # moods
    mood_phrases = [
        MOOD_MAP[mood]
        for mood in request.moods
    ]

    prompt_parts.append(
        join_phrases(
            mood_phrases
        )
    )


    # style
    prompt_parts.append(
        STYLE_MAP[
            request.style
        ]
    )


    # instruments
    if request.instruments:

        instrument_phrases = [
            INSTRUMENT_MAP[instrument]
            for instrument
            in request.instruments
        ]

        prompt_parts.append(
            join_phrases(
                instrument_phrases
            )
        )


    # natureSound
    nature_phrase = (
        NATURE_SOUND_MAP[
            request.natureSound
        ]
    )

    if nature_phrase:

        prompt_parts.append(
            nature_phrase
        )


    # tempo
    prompt_parts.append(
        TEMPO_MAP[
            request.tempo
        ]
    )


    # textures
    texture_phrases = [
        TEXTURE_MAP[texture]
        for texture
        in request.textures
    ]

    texture_text = join_phrases(
        texture_phrases
    )

    prompt_parts.append(
        f"{texture_text} sound texture"
    )


    # scene
    if request.scene:

        scene_phrase = (
            SCENE_MAP[
                request.scene
            ]
        )

        prompt_parts.append(
            f"{scene_phrase} atmosphere"
        )


    # freeText
    cleaned_free_text = (
        clean_free_text(
            request.freeText
        )
    )

    if cleaned_free_text:

        prompt_parts.append(
            "additional preference: "
            + cleaned_free_text
        )


    # 固定條件
    prompt_parts.append(
        "instrumental"
    )

    prompt_parts.append(
        "no vocals"
    )


    prompt = ", ".join(
        prompt_parts
    )


    if prompt:

        prompt = (
            prompt[0].upper()
            + prompt[1:]
        )


    return prompt + "."


# ============================================================
# 10. 中文 Description Builder
# ============================================================

def build_description_zh(
    request: GenerateMusicRequest
) -> str:

    # --------------------------------------------------------
    # 情緒
    # --------------------------------------------------------

    moods = [
        MOOD_ZH_MAP[mood]
        for mood in request.moods
    ]

    mood_text = join_zh(
        moods
    )


    # --------------------------------------------------------
    # 音樂風格
    # --------------------------------------------------------

    style_text = (
        STYLE_ZH_MAP[
            request.style
        ]
    )


    description = (
        f"{mood_text}"
        f"{style_text}風格的音樂"
    )


    # --------------------------------------------------------
    # 樂器
    # --------------------------------------------------------

    # if request.instruments:

    #     instruments = [
    #         INSTRUMENT_ZH_MAP[
    #             instrument
    #         ]
    #         for instrument
    #         in request.instruments
    #     ]

    #     description += (
    #         f"，以{join_zh(instruments)}"
    #         f"為主要聲音元素"
    #     )


    # --------------------------------------------------------
    # 自然聲
    # --------------------------------------------------------

    # nature_sound = (
    #     NATURE_SOUND_ZH_MAP[
    #         request.natureSound
    #     ]
    # )

    # if nature_sound:

    #     description += (
    #         f"，搭配{nature_sound}環境聲"
    #     )


    # --------------------------------------------------------
    # 節奏
    # --------------------------------------------------------

    # tempo_text = (
    #     TEMPO_ZH_MAP[
    #         request.tempo
    #     ]
    # )

    # description += (
    #     f"，採用{tempo_text}的節奏"
    # )


    # --------------------------------------------------------
    # 聲音質感
    # --------------------------------------------------------

    # textures = [
    #     TEXTURE_ZH_MAP[
    #         texture
    #     ]
    #     for texture
    #     in request.textures
    # ]

    # description += (
    #     f"，呈現{join_zh(textures)}"
    #     f"的聲音質感"
    # )


    # --------------------------------------------------------
    # 場景
    # --------------------------------------------------------

    # if request.scene:

    #     scene_text = (
    #         SCENE_ZH_MAP[
    #             request.scene
    #         ]
    #     )

    #     description += (
    #         f"，營造{scene_text}的氛圍"
    #     )

    return description


# ============================================================
# 11. 將 request 整理成 Firestore settings
# ============================================================

def build_settings_data(
    request: GenerateMusicRequest
) -> dict:

    return {
        "moods":
            request.moods,

        "style":
            request.style,

        "tempo":
            request.tempo,

        "textures":
            request.textures,

        "instruments":
            request.instruments,

        "natureSound":
            request.natureSound,

        "scene":
            request.scene or None,

        "freeText":
            clean_free_text(
                request.freeText
            )
    }

# ============================================================
# 12. Firebase / Music 儲存工具
# ============================================================

def build_music_id(
    generation_id: str,
    song: dict,
    index: int
) -> str:
    """
    為每首 Suno 歌曲建立穩定的 musicId。

    使用 generationId + Suno song id 建立 UUID5，
    這樣即使 /status 被重複呼叫，也不會一直建立新的 musicId。
    """

    suno_song_id = song.get("id")

    if not suno_song_id:
        suno_song_id = f"song_{index}"

    stable_source = (
        f"{generation_id}:"
        f"{suno_song_id}:"
        f"{index}"
    )

    music_uuid = uuid.uuid5(
        uuid.NAMESPACE_URL,
        stable_source
    )

    return (
        "music_"
        + music_uuid.hex
    )


def download_file(
    url: str,
    file_name: str
) -> tuple[bytes, str]:
    """
    從 Suno / 第三方 URL 下載檔案。

    回傳：
    (
        bytes,
        content_type
    )
    """

    if not url:
        raise RuntimeError(
            f"{file_name} 的下載 URL 為空"
        )

    try:

        response = requests.get(
            url,
            timeout=120
        )

        response.raise_for_status()

    except requests.RequestException as e:

        raise RuntimeError(
            f"下載 {file_name} 失敗：{str(e)}"
        )


    content_type = (
        response.headers.get(
            "Content-Type"
        )
        or "application/octet-stream"
    )

    return (
        response.content,
        content_type
    )


def upload_music_files(
    music_id: str,
    audio_url: str,
    image_url: str
) -> tuple[str, str]:
    """
    下載 Suno MP3 / Cover，
    並上傳到 Firebase Storage。

    Storage：
    music/{musicId}/audio.mp3
    music/{musicId}/cover.jpg
    """

    # --------------------------------------------------------
    # 下載 Audio
    # --------------------------------------------------------

    audio_bytes, audio_content_type = (
        download_file(
            audio_url,
            "audio.mp3"
        )
    )


    # --------------------------------------------------------
    # 下載 Cover
    # --------------------------------------------------------

    image_bytes, image_content_type = (
        download_file(
            image_url,
            "cover.jpg"
        )
    )


    # --------------------------------------------------------
    # Storage Path
    # --------------------------------------------------------

    audio_path = (
        f"music/{music_id}/audio.mp3"
    )

    image_path = (
        f"music/{music_id}/cover.jpg"
    )


    # --------------------------------------------------------
    # 上傳 Audio
    # --------------------------------------------------------

    audio_blob = bucket.blob(
        audio_path
    )

    audio_blob.upload_from_string(
        audio_bytes,
        content_type=(
            audio_content_type
            if audio_content_type
            else "audio/mpeg"
        )
    )


    # --------------------------------------------------------
    # 上傳 Cover
    # --------------------------------------------------------

    image_blob = bucket.blob(
        image_path
    )

    image_blob.upload_from_string(
        image_bytes,
        content_type=(
            image_content_type
            if image_content_type
            else "image/jpeg"
        )
    )


    print(
        f"✅ Storage 上傳完成：{music_id}"
    )


    return (
        audio_path,
        image_path
    )


def get_saved_songs(
    music_ids: list[str]
) -> list[dict]:
    """
    generation 已經 success 時，
    直接從 Firestore musics 讀取結果。

    避免重複下載 / 上傳。
    """

    songs = []


    for music_id in music_ids:

        music_snapshot = (
            db
            .collection("musics")
            .document(music_id)
            .get()
        )


        if not music_snapshot.exists:
            continue


        music_data = (
            music_snapshot.to_dict()
        )


        songs.append({
            "musicId":
                music_data.get(
                    "musicId"
                ),

            "title":
                music_data.get(
                    "title"
                ),

            "description":
                music_data.get(
                    "description"
                ),

            "category":
                music_data.get(
                    "category"
                ),

            "durationSeconds":
                music_data.get(
                    "durationSeconds"
                ),

            "audioPath":
                music_data.get(
                    "audioPath"
                ),

            "imagePath":
                music_data.get(
                    "imagePath"
                )
        })


    return songs


# ============================================================
# 13. 測試 Server
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "message":
            "Lumi Music API is running"
    }

# ============================================================
# 14. 開始生成音樂
# ============================================================

@app.post("/api/music/generate")
def generate_music(
    request: GenerateMusicRequest,
    authorization: Optional[str] =
        Header(default=None)
):

    # --------------------------------------------------------
    # Firebase Authentication
    # --------------------------------------------------------

    current_uid = get_current_uid(
            authorization
        )


    print(
        "✅ Firebase 使用者驗證成功：",
        current_uid
    )

    # --------------------------------------------------------
    # 14-1. 驗證標籤
    # --------------------------------------------------------

    validate_music_request(
        request
    )


    # --------------------------------------------------------
    # 14-2. 建立 Prompt
    # --------------------------------------------------------

    prompt = build_prompt(
        request
    )


    # --------------------------------------------------------
    # 14-3. 建立中文 Description
    #
    # description 不存 musicGenerations，
    # 等 musics 建立時再正式寫入。
    # --------------------------------------------------------

    description_zh = (
        build_description_zh(
            request
        )
    )


    print(
        "Suno Prompt:",
        prompt
    )

    print(
        "中文 Description:",
        description_zh
    )


    # --------------------------------------------------------
    # 14-4. 建立 generationId
    # --------------------------------------------------------

    generation_id = (
        "gen_"
        + uuid.uuid4().hex
    )


    generation_ref = (
        db
        .collection(
            "musicGenerations"
        )
        .document(
            generation_id
        )
    )


    # --------------------------------------------------------
    # 14-5. 先建立 Firestore Generation
    # --------------------------------------------------------

    generation_data = {

        "generationId":
            generation_id,

        "userId":
            current_uid,

        # Suno 成功建立 task 後再更新
        "sunoTaskId":
            None,

        "status":
            "generating",

        "settings":
            build_settings_data(
                request
            ),

        "prompt":
            prompt,

        "promptVersion":
            "v1",

        "musicIds":
            [],

        "createdAt":
            firestore.SERVER_TIMESTAMP,

        "completedAt":
            None
    }


    try:

        generation_ref.set(
            generation_data
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "建立 musicGenerations "
                "失敗："
                + str(e)
            )
        )


    print(
        "✅ musicGenerations 建立成功:",
        generation_id
    )


    # --------------------------------------------------------
    # 14-6. 呼叫 Suno
    # --------------------------------------------------------

    headers = {
        "Authorization":
            f"Bearer {SUNO_API_KEY}",

        "Content-Type":
            "application/json"
    }


    payload = {
        "prompt":
            prompt,

        "customMode":
            False,

        "instrumental":
            True,

        "model":
            "V4_5ALL",

        "callBackUrl":
            "https://example.com/callback"
    }


    try:

        response = requests.post(
            f"{BASE_URL}/api/v1/generate",
            json=payload,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        result = response.json()


    except requests.RequestException as e:

        # Suno 呼叫本身失敗
        generation_ref.update({
            "status":
                "failed",

            "completedAt":
                firestore.SERVER_TIMESTAMP
        })

        raise HTTPException(
            status_code=502,
            detail=(
                "呼叫 Suno API 失敗："
                + str(e)
            )
        )


    # --------------------------------------------------------
    # 14-7. Suno 回報 API Error
    # --------------------------------------------------------

    if (
        result.get("code") != 200
        or result.get("data") is None
    ):

        generation_ref.update({
            "status":
                "failed",

            "completedAt":
                firestore.SERVER_TIMESTAMP
        })


        raise HTTPException(
            status_code=400,
            detail=result.get(
                "msg",
                "Suno API 發生未知錯誤"
            )
        )


    # --------------------------------------------------------
    # 14-8. 取得 taskId
    # --------------------------------------------------------

    suno_task_id = (
        result["data"]["taskId"]
    )


    # --------------------------------------------------------
    # 14-9. 更新 Firestore Suno Task ID
    # --------------------------------------------------------

    generation_ref.update({
        "sunoTaskId":
            suno_task_id
    })


    # --------------------------------------------------------
    # 14-10. 回傳
    #
    # Unity 之後只需要 generationId。
    # 現在 prompt / description 保留 Debug。
    # --------------------------------------------------------

    return {

        "success":
            True,

        "status":
            "generating",

        "generationId":
            generation_id,

        "prompt":
            prompt,

        "description":
            description_zh
    }


# ============================================================
# 15. 查詢音樂生成狀態
#
# Unity 傳 generationId，
# FastAPI 自己去 Firestore 找 sunoTaskId。
# ============================================================

@app.get(
    "/api/music/status/{generation_id}"
)
def get_music_status(
    generation_id: str
):

    # --------------------------------------------------------
    # 15-1. 找到 Generation
    # --------------------------------------------------------

    generation_ref = (
        db
        .collection(
            "musicGenerations"
        )
        .document(
            generation_id
        )
    )


    generation_snapshot = (
        generation_ref.get()
    )


    if not generation_snapshot.exists:

        raise HTTPException(
            status_code=404,
            detail=(
                "找不到 generationId："
                + generation_id
            )
        )


    generation_data = (
        generation_snapshot.to_dict()
    )


    generation_status = (
        generation_data.get(
            "status"
        )
    )


    music_ids = (
        generation_data.get(
            "musicIds"
        )
        or []
    )


    # --------------------------------------------------------
    # 15-2. 已經成功存過
    #
    # 避免 Unity 重複 polling 時，
    # 再次上傳 MP3 / 建立 musics。
    # --------------------------------------------------------

    if (
        generation_status
        == "success"
        and len(music_ids) > 0
    ):

        songs = get_saved_songs(
            music_ids
        )

        return {

            "success":
                True,

            "status":
                "success",

            "generationId":
                generation_id,

            "songs":
                songs
        }


    # --------------------------------------------------------
    # 15-3. 已經失敗
    # --------------------------------------------------------

    if generation_status == "failed":

        return {

            "success":
                False,

            "status":
                "failed",

            "generationId":
                generation_id,

            "songs":
                []
        }


    # --------------------------------------------------------
    # 15-4. 取得 Suno taskId
    # --------------------------------------------------------

    suno_task_id = (
        generation_data.get(
            "sunoTaskId"
        )
    )


    if not suno_task_id:

        raise HTTPException(
            status_code=500,
            detail=(
                "musicGenerations "
                "沒有 sunoTaskId"
            )
        )


    # --------------------------------------------------------
    # 15-5. 查詢 Suno
    # --------------------------------------------------------

    headers = {
        "Authorization":
            f"Bearer {SUNO_API_KEY}"
    }


    try:

        response = requests.get(
            (
                f"{BASE_URL}"
                "/api/v1/generate/"
                "record-info"
            ),

            params={
                "taskId":
                    suno_task_id
            },

            headers=
                headers,

            timeout=
                30
        )


        response.raise_for_status()

        result = (
            response.json()
        )


        print(
            "========== "
            "Suno Status Response "
            "=========="
        )

        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            )
        )

        print(
            "=============================="
            "=============="
        )


    except requests.RequestException as e:

        raise HTTPException(
            status_code=502,
            detail=(
                "查詢 Suno API 失敗："
                + str(e)
            )
        )


    data = result.get(
        "data"
    )


    if data is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "Suno 沒有回傳 task 資料"
            )
        )


    suno_status = data.get(
        "status"
    )


    # --------------------------------------------------------
    # 15-6. 還在生成
    # --------------------------------------------------------

    if (
        suno_status
        in PROCESSING_STATUSES
    ):

        # Firestore 統一使用 generating，
        # 不保存 PENDING / TEXT_SUCCESS 等第三方狀態。
        if (
            generation_status
            != "generating"
        ):
            generation_ref.update({
                "status":
                    "generating"
            })


        return {

            "success":
                True,

            "status":
                "generating",

            "generationId":
                generation_id,

            # Debug 用
            "sunoStatus":
                suno_status,

            "songs":
                []
        }


    # --------------------------------------------------------
    # 15-7. Suno 生成失敗
    # --------------------------------------------------------

    if (
        suno_status
        in FAILED_STATUSES
    ):

        generation_ref.update({

            "status":
                "failed",

            "completedAt":
                firestore.SERVER_TIMESTAMP
        })


        return {

            "success":
                False,

            "status":
                "failed",

            "generationId":
                generation_id,

            "sunoStatus":
                suno_status,

            "errorCode":
                data.get(
                    "errorCode"
                ),

            "errorMessage":
                data.get(
                    "errorMessage"
                ),

            "songs":
                []
        }


    # --------------------------------------------------------
    # 15-8. 未知 Suno 狀態
    #
    # 不直接把 Generation 判定 failed，
    # 避免未來 Suno 新增中間狀態。
    # --------------------------------------------------------

    if suno_status not in READY_STATUSES:

        return {

            "success":
                False,

            "status":
                "unknown",

            "generationId":
                generation_id,

            "sunoStatus":
                suno_status,

            "songs":
                [],

            "message":
                "收到未知的 Suno 任務狀態"
        }


    # ========================================================
    # 15-9. Suno SUCCESS
    # ========================================================

    suno_data = (
        data
        .get(
            "response",
            {}
        )
        .get(
            "sunoData",
            []
        )
    )


    # --------------------------------------------------------
    # 找出目前真正可以使用的歌曲
    #
    # FIRST_SUCCESS 時可能只有其中一首已經具有完整資料，
    # 所以不要單純假設 sunoData[0] 一定完整。
    # --------------------------------------------------------

    available_songs = []

    for song in suno_data:

        audio_url = song.get(
            "audioUrl"
        )

        image_url = song.get(
            "imageUrl"
        )

        duration = song.get(
            "duration"
        )


        if (
            audio_url
            and image_url
            and duration is not None
        ):

            available_songs.append(
                song
            )


    # --------------------------------------------------------
    # FIRST_SUCCESS 但歌曲資料還沒完整
    #
    # 不判定失敗，Unity 繼續 polling。
    # --------------------------------------------------------

    if not available_songs:

        if suno_status == "FIRST_SUCCESS":

            return {

                "success":
                    True,

                "status":
                    "generating",

                "generationId":
                    generation_id,

                "sunoStatus":
                    suno_status,

                "songs":
                    []
            }


        # SUCCESS 還沒有任何可用歌曲就屬於異常
        raise HTTPException(
            status_code=500,
            detail=(
                "Suno SUCCESS，"
                "但沒有完整的歌曲資料"
            )
        )


    # --------------------------------------------------------
    # Lumi 只需要第一首
    # --------------------------------------------------------

    selected_song = (
        available_songs[0]
    )

    selected_suno_data = [
        selected_song
    ]


    # --------------------------------------------------------
    # 15-10. Generation → saving
    # --------------------------------------------------------

    generation_ref.update({
        "status":
            "saving"
    })


    # --------------------------------------------------------
    # 15-11. 從 Firestore settings 重建 Request
    #
    # 用來產生中文 Description。
    # --------------------------------------------------------

    settings = (
        generation_data.get(
            "settings"
        )
        or {}
    )


    try:

        saved_request = (
            GenerateMusicRequest(
                **settings
            )
        )

    except Exception as e:

        generation_ref.update({

            "status":
                "failed",

            "completedAt":
                firestore.SERVER_TIMESTAMP
        })

        raise HTTPException(
            status_code=500,
            detail=(
                "無法從 settings "
                "重建 GenerateMusicRequest："
                + str(e)
            )
        )


    description_zh = (
        build_description_zh(
            saved_request
        )
    )


    owner_user_id = (
        generation_data.get(
            "userId"
        )
    )


    category = (
        MOOD_ZH_MAP[
            saved_request.moods[0]
        ]
    )


    # --------------------------------------------------------
    # 15-12. 儲存每一首歌曲
    # --------------------------------------------------------

    saved_music_data = []


    try:

        for index, song in enumerate(
            selected_suno_data
        ):

            # ------------------------------------------------
            # 產生穩定 musicId
            # ------------------------------------------------

            music_id = build_music_id(
                generation_id,
                song,
                index
            )


            # ------------------------------------------------
            # Suno 結果
            # ------------------------------------------------

            title = (
                song.get("title")
                or "Untitled"
            )

            audio_url = (
                song.get(
                    "audioUrl"
                )
            )

            image_url = (
                song.get(
                    "imageUrl"
                )
            )

            duration = (
                song.get(
                    "duration"
                )
            )


            if not audio_url:

                raise RuntimeError(
                    f"{music_id} "
                    "沒有 audioUrl"
                )


            if not image_url:

                raise RuntimeError(
                    f"{music_id} "
                    "沒有 imageUrl"
                )


            if duration is None:

                raise RuntimeError(
                    f"{music_id} "
                    "沒有 duration"
                )


            # ------------------------------------------------
            # 上傳 Storage
            # ------------------------------------------------

            (
                audio_path,
                image_path
            ) = upload_music_files(

                music_id=
                    music_id,

                audio_url=
                    audio_url,

                image_url=
                    image_url
            )


            # ------------------------------------------------
            # 準備 Firestore musics
            # ------------------------------------------------

            music_data = {

                "musicId":
                    music_id,

                "generationId":
                    generation_id,

                "ownerUserId":
                    owner_user_id,

                "title":
                    title,

                # 中文 Description
                "description":
                    description_zh,

                # 使用 mood 的中文名稱作為 category
                "category":
                    category,

                "durationSeconds":
                    float(duration),

                "audioPath":
                    audio_path,

                "imagePath":
                    image_path,

                "createdAt":
                    firestore.SERVER_TIMESTAMP
            }


            saved_music_data.append(
                (
                    music_id,
                    music_data
                )
            )


    except Exception as e:

        # Storage / Download 任一失敗
        generation_ref.update({

            "status":
                "failed",

            "completedAt":
                firestore.SERVER_TIMESTAMP
        })


        print(
            "❌ 儲存 Suno 音樂失敗：",
            str(e)
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "Suno 已生成成功，"
                "但保存 Firebase 失敗："
                + str(e)
            )
        )


    # --------------------------------------------------------
    # 15-13. Firestore Batch
    #
    # musics + generation 最後一起提交。
    # --------------------------------------------------------

    music_ids = [
        music_id
        for music_id, _
        in saved_music_data
    ]


    batch = db.batch()


    for (
        music_id,
        music_data
    ) in saved_music_data:

        music_ref = (
            db
            .collection(
                "musics"
            )
            .document(
                music_id
            )
        )


        batch.set(
            music_ref,
            music_data
        )


    batch.update(

        generation_ref,

        {
            "status":
                "success",

            "musicIds":
                music_ids,

            "completedAt":
                firestore.SERVER_TIMESTAMP
        }
    )


    try:

        batch.commit()

    except Exception as e:

        # Storage 已經上傳，
        # 但 Firestore Batch 失敗。
        #
        # generation 保持 saving，
        # 下次 /status 可使用相同 musicId 重試，
        # 不會產生不同 ID。
        print(
            "❌ Firestore Batch 儲存失敗：",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Storage 已完成，"
                "但 Firestore 儲存失敗："
                + str(e)
            )
        )


    print(
        "✅ Generation 儲存全部完成：",
        generation_id
    )


    # --------------------------------------------------------
    # 15-14. 回傳 Unity
    # --------------------------------------------------------

    songs = []


    for (
        music_id,
        music_data
    ) in saved_music_data:

        songs.append({

            "musicId":
                music_id,

            "title":
                music_data[
                    "title"
                ],

            "description":
                music_data[
                    "description"
                ],

            "category":
                music_data[
                    "category"
                ],

            "durationSeconds":
                music_data[
                    "durationSeconds"
                ],

            "audioPath":
                music_data[
                    "audioPath"
                ],

            "imagePath":
                music_data[
                    "imagePath"
                ]
        })


    return {

        "success":
            True,

        "status":
            "success",

        "generationId":
            generation_id,

        "songs":
            songs
    }