from fastapi import FastAPI, Request, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from datetime import datetime, timedelta, timezone

from fastapi_login import LoginManager

from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    HTTPBasicCredentials,
)
from fastapi_login.exceptions import InvalidCredentialsException
from .triplestore import (
    create_database,
    get_user,
    get_members,
    add_family_member,
    add_movie,
    find_movies,
)

from .authenticator import (
    User,
    authenticate_user,
    get_current_active_user,
    add_authentication,
    create_access_token,
    EXPIRES,
    Token,
    SECRET_KEY,
    verify_password,
)

from .utils import auto_complete

class NotAuthenticatedException(Exception):
    pass

from typing import Annotated, Dict

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="./templates")

manager = LoginManager(SECRET_KEY, "/login", use_cookie=True, not_authenticated_exception=NotAuthenticatedException)

class MemberData(BaseModel):
    username: str

class UpdateData(BaseModel):
    function: str
    data: Dict

class MovieRequest(BaseModel):
    title: str

class MovieData(BaseModel):
    member: str

@manager.user_loader()
def query_user(user_id: str):
    user = get_user(user_id)
    return user


@app.on_event("startup")
def on_startup():
    store = create_database()
    add_authentication(store)

@app.get("/", response_class=HTMLResponse)
def serve_root(
        request: Request
):
    return templates.TemplateResponse(request=request, name="index.html") #context={"data:data"})

@app.post("/update/")
def process_update(update_data: UpdateData, user=Depends(manager)):
    print(update_data)
    print(user)
    match update_data.function:
        case "add_family_member":
            add_family_member(user["user_node"], update_data.data["name"])
            return "Successful"
        case "add_movie":
            add_movie(
                user["user_node"],
                update_data.data["member"],
                update_data.data["movie-id"],
                update_data.data["movie-name"],
                update_data.data["date"],
                poster_url=update_data.data["poster-id"]
            )
        case _:
            return "Not Successful"


@app.post("/movies")
def movie_endpoint(movie_data: MovieData, user=Depends(manager)):
    """ """
    return find_movies(user["user_node"], movie_data.member)


@app.exception_handler(NotAuthenticatedException)
def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login")


@app.get("/movies")
async def show_past_movies(request: Request, user=Depends(manager)):
    return templates.TemplateResponse(request, name="movies.html")

@app.get("/home")
async def show_home(request: Request, user=Depends(manager)):
    print(user)
    data = get_members(user["user_node"])
    print(data)
    return templates.TemplateResponse(request, context={"members": data}, name="home.html")

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, name="login.html")

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    """
    #user = authenticate_user(form_data.username, form_data.password)
    print("form-data", form_data)

    user = query_user(form_data.username)
    print(user)

    if not user:
        raise InvalidCredentialsException
    if not verify_password(form_data.password, user["hashed_password"]):
        raise InvalidCredentialsException
    access_token = manager.create_access_token(data={"sub": form_data.username})

    response = RedirectResponse(url="/home",status_code=status.HTTP_302_FOUND)
    manager.set_cookie(response, access_token)
    return response
    #return {"access_token": access_token}


@app.post("/mdb")
async def search_mdb(request: MovieRequest, user=Depends(manager)):
    response = await auto_complete(request.title)
    #print(response)
    return response

