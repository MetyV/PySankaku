from pydantic import BaseModel, Field
from typing import Optional

class AccountData(BaseModel):
    '''
    Descriptions in future
    '''
    id               : Optional[str]  = Field(None, description='')
    name             : Optional[str]  = Field(None, description='User name')
    display_name     : Optional[str]  = Field(None, description='[EDITABLE] Displayed name')
    level            : Optional[int]  = Field(None, description='')
    email            : Optional[str]  = Field(None, description='')
    filter_content   : Optional[bool] = Field(None, description='[EDITABLE] Hide sensitive content')
    is_verified      : Optional[bool] = Field(None, description='')
    favs_are_private : Optional[bool] = Field(None, description='[EDITABLE] Keep favs and other activity private')
    avatar_url       : Optional[str]  = Field(None, description='[EDITABLE]') # like https://s.sankakucomplex.com/a/{accoutnRealId}.webp

    hide_ads                  : Optional[bool]                 = Field(None, description='')
    subscription_level        : Optional[int]                  = Field(None, description='')
    has_mail                  : Optional[bool]                 = Field(None, description='')
    email_verification_status : Optional[str]                  = Field(None, description='')
    verifications_count       : Optional[int]                  = Field(None, description='')
    blacklist_is_hidden       : Optional[bool]                 = Field(None, description='')
    limit_blacklist_rule      : Optional[int]                  = Field(None, description='')
    blacklisted_contents      : Optional[list]                 = Field(None, description='')
    blacklisted_tags          : Optional[list]                 = Field(None, description='')
    blacklisted               : Optional[list[str]]            = Field(None, description='')
    inactive_items            : Optional[list]                 = Field(None, description='')
    credits                   : Optional[int]                  = Field(None, description='')
    credits_subs              : Optional[int]                  = Field(None, description='')
    points                    : Optional[int]                  = Field(None, description='')
    subscription_points       : Optional[int]                  = Field(None, description='')
    blacklist_tags_system     : Optional[list]                 = Field(None, description='')
    real_id                   : Optional[int]                  = Field(None, description='')
    creator_registration_group: Optional[str]                  = Field(None, description='')  # idk
    is_tag_creator            : Optional[bool]                 = Field(None, description='')
    is_skip_passkey           : Optional[bool]                 = Field(None, description='')
    payment_processor         : Optional[str]                  = Field(None, description='')
    content_restriction_bypass: Optional[bool]                 = Field(None, description='')
    mfa_method                : Optional[int]                  = Field(None, description='')
    mfa_invalid_times         : Optional[int]                  = Field(None, description='')
    mfa_unblocked_at          : Optional[int]                  = Field(None, description='')  # idk
    last_logged_in_at         : Optional[str]                  = Field(None, description='')  # like "2026-08-09T10:47:25.165Z"
    favorite_count            : Optional[int]                  = Field(None, description='')
    post_favorite_count       : Optional[int]                  = Field(None, description='')
    pool_favorite_count       : Optional[int]                  = Field(None, description='')
    companion_favorite_count  : Optional[int]                  = Field(None, description='')
    collection_favorite_count : Optional[int]                  = Field(None, description='')
    vote_count                : Optional[int]                  = Field(None, description='')
    post_vote_count           : Optional[int]                  = Field(None, description='')
    pool_vote_count           : Optional[int]                  = Field(None, description='')
    companion_vote_count      : Optional[int]                  = Field(None, description='')
    collection_vote_count     : Optional[int]                  = Field(None, description='')
    subscriptions             : Optional[list]                 = Field(None, description='')
    created_at                : Optional[str]                  = Field(None, description='')  # like "2023-07-29T19:49:19.319Z"
    avatar_rating             : Optional[str]                  = Field(None, description='')
    post_upload_count         : Optional[int]                  = Field(None, description='')
    pool_upload_count         : Optional[int]                  = Field(None, description='')
    companion_upload_count    : Optional[int]                  = Field(None, description='')
    collection_upload_count   : Optional[int]                  = Field(None, description='')
    comment_count             : Optional[int]                  = Field(None, description='')
    post_update_count         : Optional[int]                  = Field(None, description='')
    note_update_count         : Optional[int]                  = Field(None, description='')
    wiki_update_count         : Optional[int]                  = Field(None, description='')
    pool_update_count         : Optional[int]                  = Field(None, description='')
    series_update_count       : Optional[int]                  = Field(None, description='')
    tag_update_count          : Optional[int]                  = Field(None, description='')
    companion_update_count    : Optional[int]                  = Field(None, description='')
    collection_update_count   : Optional[int]                  = Field(None, description='')
    forum_post_count          : Optional[int]                  = Field(None, description='')
    artist_update_count       : Optional[int]                  = Field(None, description='')
    reputation_level          : Optional[ReputationLevelModel] = Field(None, description='')

class ReputationLevelModel(BaseModel):
    level   : int = Field(..., description='')
    total   : int = Field(..., description='')
    progress: int = Field(..., description='')