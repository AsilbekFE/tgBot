import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("movie-db")
BASE_DIR = Path(__file__).parent
MOVIES_FILE = BASE_DIR / "movies.json"
USERS_FILE = BASE_DIR / "users.json"
ADMIN_IDS = [8551800192, 8679491064]
OWNER_ID = 8551800192


def is_admin(user_id: int) -> bool:
    try:
        return int(user_id) in ADMIN_IDS
    except Exception:
        return False


# Standart dastlabki kinolar
INITIAL_MOVIES = [
    {
        "id": "m_101",
        "code": "101",
        "title": "Forsaj 10 (Fast X)",
        "description": "Dom Toretto va uning oilasi bu safar Dante Reyesga qarshi eng xavfli jangga kirishadi. Jangari, poyga va sarguzasht.",
        "poster_url": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "created_at": "2026-10-16 23:00",
    },
    {
        "id": "m_102",
        "code": "102",
        "title": "Avatar 2: Suv Yo'li",
        "description": "Jeyk Salli va Neytiri Pandoraning yangi okean xalqlari bilan birlashib, insonlar bosqiniga qarshi kurashadilar.",
        "poster_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
        "created_at": "2026-10-16 23:05",
    },
    {
        "id": "m_103",
        "code": "103",
        "title": "Qasoskorlar: Intiho",
        "description": "Tanos koinot aholisining yarmini yo'q qilgandan so'ng, qolgan Qasoskorlar vaqt bo'ylab sayohat qilishadi.",
        "poster_url": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=600",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "created_at": "2026-10-16 23:10",
    },
]

INITIAL_USERS = [
    {
        "id": 8551800192,
        "first_name": "Asilbek",
        "last_name": "Sadullayev",
        "username": "asl_o_1",
        "is_admin": True,
        "is_premium": True,
        "status": "active",
        "registered_at": "2026-10-16 22:40",
    },
    {
        "id": 8679491064,
        "first_name": "Afruz",
        "last_name": "",
        "username": "Afruz0886",
        "is_admin": True,
        "is_premium": True,
        "status": "active",
        "registered_at": "2026-10-17 17:09",
    },
]


def load_movies() -> list[dict]:
    if not MOVIES_FILE.exists():
        save_movies(INITIAL_MOVIES)
        return list(INITIAL_MOVIES)
    try:
        with open(MOVIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("movies.json yuklashda xatolik")
        return []


def save_movies(movies: list[dict]) -> None:
    try:
        with open(MOVIES_FILE, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("movies.json saqlashda xatolik")


def get_movie_by_code(code: str) -> Optional[dict]:
    code_clean = str(code).strip().lower()
    for m in load_movies():
        if str(m.get("code")).strip().lower() == code_clean:
            return m
    return None


def add_movie(
    title: str,
    code: str,
    description: str,
    poster_url: str = "",
    video_url: str = "",
    video_file: str = "",
    telegram_file_id: Optional[str] = None,
) -> dict:
    movies = load_movies()
    clean_code = str(code).strip()
    for m in movies:
        if str(m.get("code")).strip() == clean_code:
            raise ValueError(f"Ushbu '{clean_code}' kodli kino allaqachon mavjud!")

    new_movie = {
        "id": f"m_{clean_code}_{int(datetime.now().timestamp())}",
        "code": clean_code,
        "title": title.strip(),
        "description": description.strip(),
        "poster_url": poster_url.strip() if poster_url else "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600",
        "video_url": video_url.strip(),
        "video_file": video_file.strip(),
        "telegram_file_id": telegram_file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    movies.insert(0, new_movie)
    save_movies(movies)
    return new_movie


def update_movie(updated_movie: dict) -> bool:
    movies = load_movies()
    for idx, m in enumerate(movies):
        if m.get("id") == updated_movie.get("id") or str(m.get("code")) == str(updated_movie.get("code")):
            movies[idx] = updated_movie
            save_movies(movies)
            return True
    return False


def delete_movie(movie_id: str) -> bool:
    movies = load_movies()
    orig_len = len(movies)
    movies = [m for m in movies if m.get("id") != movie_id and m.get("code") != movie_id]
    if len(movies) != orig_len:
        save_movies(movies)
        return True
    return False


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        save_users(INITIAL_USERS)
        return list(INITIAL_USERS)
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            # Adminlar har doim admin va active
            changed = False
            for aid in ADMIN_IDS:
                found = False
                for u in users:
                    if u.get("id") == aid:
                        if not u.get("is_admin") or not u.get("is_premium") or u.get("status") != "active":
                            u["is_admin"] = True
                            u["is_premium"] = True
                            u["status"] = "active"
                            changed = True
                        found = True
                        break
                if not found:
                    default_u = next((x for x in INITIAL_USERS if x["id"] == aid), {
                        "id": aid,
                        "first_name": f"Admin ({aid})",
                        "last_name": "",
                        "username": "",
                        "is_admin": True,
                        "is_premium": True,
                        "status": "active",
                        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    users.insert(0, default_u)
                    changed = True
            if changed:
                save_users(users)
            return users
    except Exception:
        log.exception("users.json yuklashda xatolik")
        return []


def save_users(users: list[dict]) -> None:
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("users.json saqlashda xatolik")


def get_user(user_id: int) -> Optional[dict]:
    for u in load_users():
        if u.get("id") == user_id:
            return u
    return None


def register_or_get_user(user_id: int, first_name: str = "", last_name: str = "", username: str = "") -> dict:
    users = load_users()
    for u in users:
        if u.get("id") == user_id:
            # Ma'lumotlarni yangilash
            if first_name:
                u["first_name"] = first_name
            if last_name:
                u["last_name"] = last_name
            if username:
                u["username"] = username
            if is_admin(user_id):
                u["is_admin"] = True
                u["is_premium"] = True
                u["status"] = "active"
            save_users(users)
            return u

    user_admin = is_admin(user_id)
    new_user = {
        "id": user_id,
        "first_name": first_name or "Foydalanuvchi",
        "last_name": last_name or "",
        "username": username or "",
        "is_admin": user_admin,
        "is_premium": user_admin,
        "status": "active" if user_admin else "inactive",
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    users.append(new_user)
    save_users(users)
    return new_user


def toggle_user_status(user_id: int, new_status: Optional[str] = None) -> dict:
    users = load_users()
    for u in users:
        if u.get("id") == user_id:
            if is_admin(user_id):
                u["status"] = "active"
                u["is_premium"] = True
                save_users(users)
                return u

            if new_status:
                u["status"] = new_status
            else:
                u["status"] = "inactive" if u.get("status") == "active" else "active"

            u["is_premium"] = (u["status"] == "active")
            save_users(users)
            return u

    raise ValueError(f"Foydalanuvchi {user_id} topilmadi.")


def activate_user_payment(user_id: int, card_last4: str = "7604") -> dict:
    users = load_users()
    for u in users:
        if u.get("id") == user_id:
            u["status"] = "active"
            u["is_premium"] = True
            u["paid_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            u["card_last4"] = card_last4
            save_users(users)
            return u

    # Agar user hali ro'yxatdan o'tmagan bo'lsa
    new_user = {
        "id": user_id,
        "first_name": "Premium Foydalanuvchi",
        "last_name": "",
        "username": "",
        "is_admin": user_id == OWNER_ID,
        "is_premium": True,
        "status": "active",
        "paid_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "card_last4": card_last4,
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    users.append(new_user)
    save_users(users)
    return new_user
