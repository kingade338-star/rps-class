import random
from fastapi import FastAPI, Request, HTTPException, status, Depends, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from schemas import GameHistoryResponse, UserResponse

from sqlalchemy import select
from sqlalchemy.orm import Session
import models
from database import get_db, Base, engine

from typing import Annotated

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")

CHOICES = ["Rock", "Paper", "Scissors"]

BEATS = {
    "Rock": "Paper",
    "Paper": "Scissors",
    "Scissors": "Rock",
}

def get_result(user_choice: str, computer_choice: str) -> str:
    if user_choice == computer_choice:
        return "Draw"
    if BEATS[user_choice] == computer_choice:
        return "Lose"
    return "Win"

def get_logged_in_user_id(request: Request):
    uid = request.cookies.get("user_id")
    return int(uid) if uid and uid.isdigit() else None


# ── login.html ────────────────────────────────────────────────

@app.get("/", include_in_schema=False, name="login_page")
def login_page(request: Request):
    if get_logged_in_user_id(request):
        return RedirectResponse(url="/home", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "login.html", {"title": "Login", "user": None})


@app.post("/login", include_in_schema=False)
def login(
    request: Request,
    user_id: int = Form(...),
    user_email: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.execute(
        select(models.User).where(
            models.User.id == user_id,
            models.User.email == user_email
        )
    ).scalars().first()

    if user is None:
        return templates.TemplateResponse(
            request, "login.html",
            {"title": "Login", "user": None, "error": "Invalid Player ID or email. Please try again."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url="/home", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response


@app.get("/register", include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Register", "user": None, "register_mode": True})


@app.post("/register", include_in_schema=False)
def register(
    request: Request,
    username: str = Form(...),       # ← added
    user_email: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if username already exists
    existing_username = db.execute(
        select(models.User).where(models.User.username == username)
    ).scalars().first()

    if existing_username is not None:
        return templates.TemplateResponse(
            request, "login.html",
            {"title": "Register", "user": None, "register_mode": True, "error": "Username already taken. Please choose another."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Check if email already exists
    existing_email = db.execute(
        select(models.User).where(models.User.email == user_email)
    ).scalars().first()

    if existing_email is not None:
        return templates.TemplateResponse(
            request, "login.html",
            {"title": "Register", "user": None, "register_mode": True, "error": "Email already registered. Please log in."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    new_user = models.User(username=username, email=user_email)   # ← added username
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return templates.TemplateResponse(
        request, "login.html",
        {
            "title": "Register",
            "user": None,
            "register_mode": True,
            "success": f"Account created! Welcome {new_user.username}, your Player ID is #{new_user.id} — save it, then log in.",
        },
    )


# ── home.html ─────────────────────────────────────────────────

@app.get("/home", include_in_schema=False, name="home_page")
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    uid = get_logged_in_user_id(request)
    if uid is None:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    user = db.execute(select(models.User).where(models.User.id == uid)).scalars().first()
    if user is None:
        resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        resp.delete_cookie("user_id")
        return resp

    history = db.execute(
        select(models.GameHistory)
        .where(models.GameHistory.user_id == uid)
        .order_by(models.GameHistory.id.desc())
    ).scalars().all()

    return templates.TemplateResponse(request, "home.html", {
        "title": "Dashboard",
        "user": user,
        "history": history,
        "wins":   sum(1 for h in history if str(h.result) == "Win"),
        "losses": sum(1 for h in history if str(h.result) == "Lose"),
        "draws":  sum(1 for h in history if str(h.result) == "Draw"),
    })


# ── gameplay.html ─────────────────────────────────────────────

@app.get("/gameplay", include_in_schema=False, name="gameplay_page")
def gameplay(request: Request, db: Session = Depends(get_db)):
    uid = get_logged_in_user_id(request)
    if uid is None:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    user = db.execute(select(models.User).where(models.User.id == uid)).scalars().first()
    return templates.TemplateResponse(request, "gameplay.html", {"title": "Play", "user": user})


# ── result.html ───────────────────────────────────────────────

@app.post("/play", include_in_schema=False)
def play(request: Request, choice: str = Form(...), db: Session = Depends(get_db)):
    uid = get_logged_in_user_id(request)
    if uid is None:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    if choice not in CHOICES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid choice.")

    user = db.execute(select(models.User).where(models.User.id == uid)).scalars().first()
    computer_choice = random.choice(CHOICES)
    outcome = get_result(choice, computer_choice)

    game = models.GameHistory(
        user_id=uid,
        user_choice=choice,
        computer_choice=computer_choice,
        result=outcome
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    return templates.TemplateResponse(request, "result.html", {"title": "Result", "user": user, "result": game})


# ── Logout ────────────────────────────────────────────────────

@app.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user_id")
    return response


# ── API ───────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/history", response_model=list[GameHistoryResponse])
def get_user_history(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return db.execute(
        select(models.GameHistory)
        .where(models.GameHistory.user_id == user_id)
        .order_by(models.GameHistory.id.desc())
    ).scalars().all()


# ── Error handlers ────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail or "An error occurred. Please try again."

    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exception.status_code, content={"detail": message})

    return templates.TemplateResponse(
        request, "layout.html",
        {"title": f"Error {exception.status_code}", "user": None, "error_code": exception.status_code, "error_message": message},
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exception.errors()})

    return templates.TemplateResponse(
        request, "layout.html",
        {"title": "Validation Error", "user": None, "error_code": 422, "error_message": "Invalid input. Please check your data."},
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )