from pydantic import BaseModel


class AvatarModel(BaseModel):
    post_id: str   = '' # file = False esli chto
    left   : float = 0.0
    right  : float = 0.0
    top    : float = 0.0
    bottom : float = 0.0