from typing import Annotated
from datetime import timedelta, datetime, timezone
import hashlib

from dotenv import load_dotenv, dotenv_values
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    HTTPBasic,
    HTTPBasicCredentials,
)
from fastapi import Depends, FastAPI, HTTPException, status
import os
import jwt
from jwt.exceptions import InvalidTokenError

from pwdlib import PasswordHash
from pydantic import BaseModel

from pyoxigraph import Store, Quad, Literal, QuerySolutions, BlankNode

from .triplestore import ns, get_user


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
EXPIRES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

security = HTTPBasic()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


password_hash = PasswordHash.recommended()

oath2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def add_authentication(store: Store):
    """
    This is a script for creating user credentials from the .env file.
    Updates the User to fit in the following schema:
    ```
    <user>
        a mno:User ;
        mno:userName "johndoe"^^xsd:string ;
        mno:fullName "John Doe"^^xsd:string ;
        mno:emailAddress "johndoe@example.com"^^xsd:string ;
        mno:hashedPassword "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc"^^xsd:string ;
        mno:disabled "False"^^xsd:string ;
    .
    ```
    """
    m = hashlib.sha256()
    user_graph = ns.mno.term("UserGraph")
    store.clear_graph(user_graph)
    username = os.getenv("SYSTEM_USER_NAME")
    full_name = os.getenv("SYSTEM_USER_FULLNAME")
    email = os.getenv("SYSTEM_USER_EMAIL")
    pswd = os.getenv("SYSTEM_USER_PASSWORD")

    m.update(username.encode("utf-8"))
    user_node = ns.mno.term("data/_User_" + m.hexdigest())

    store.add(Quad(user_node, ns.rdf.type, ns.mno.User, user_graph))
    store.add(Quad(user_node, ns.mno.userName, Literal(username), user_graph))
    store.add(Quad(user_node, ns.mno.fullName, Literal(full_name), user_graph))
    store.add(Quad(user_node, ns.mno.emailAddress, Literal(email), user_graph))
    store.add(
        Quad(
            user_node,
            ns.mno.hashedPassword,
            Literal(password_hash.hash(pswd)),
            user_graph,
        )
    )
    store.add(Quad(user_node, ns.mno.disabled, Literal("False"), user_graph))

    """
    Add the users default usage
    """
    store.add(Quad(user_node, ns.rdf.type, ns.mno.FamilyHead, user_node))
    store.add(Quad(user_node, ns.rdf.type, ns.mno.FamilyMember, user_node))
    store.add(Quad(user_node, ns.mno.fullName, Literal(full_name), user_node))

    choice_node = BlankNode()
    movies_graph = ns.mno.term("Movies")
    movie_node = ns.mno.term("data/_Movie_tt2908228")
    store.add(Quad(user_node, ns.mno.choice, choice_node, user_node))
    store.add(Quad(choice_node, ns.mno.movie, movie_node, user_node))
    store.add(Quad(choice_node, ns.mno.onDate, Literal("2023-03-13T10:23Z", datatype=ns.xsd.dateTime), user_node))

    store.add(Quad(movie_node, ns.dc.term("title"), Literal("My Little Pony: Equestria Grils"), movies_graph))
    store.add(Quad(movie_node, ns.dc.identifier, Literal("tt2908228"), movies_graph))

    store.flush()


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


def authenticate_user(username: str, password: str):
    # user = get_user(store, username)
    user_dict = get_user(username)
    # print(user_dict)
    if not user_dict:
        return False
    user = UserInDB(**user_dict)
    if not verify_password(password, user.hashed_password):
        return False
    return user


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    user = authenticate_user(credentials.username, credentials.password)
    if not (user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oath2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return UserInDB(**user)


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
