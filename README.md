![AI-assisted](https://img.shields.io/badge/AI--assisted-all-blue)

AI? Yes, mostly comments and logs, just a tiny bit (~15%) code.

TODO:
1. Write readme -> OK
2. More todo -> Fail
4. AI readme -> 50%
5. Tag image/video (https://sankakuapi.com/posts/tagging_image POST Authorization | https://sankakuapi.com/posts/tagging_video POST Authorization)
6. Post post (https://sankakuapi.com/posts POST Authorization)
6.1
data = {
    "post[parent_id]": "",
    "post[rating]": "e", # Chtob ne banili. mojno i 's'
    "post[tags]": '[]',
    "post[upload_url]": "",
    "post[pool_id]": "",
    "post[reupload_post_id]": ""
}
6.1 and 5.1
files = {
    "post[file]": (
        "123.jpg",
        open("123.jpg", "rb"),
        "image/jpeg"  # MIME
    )
}
response = requests.post(url, data=data, files=files)
   
   
In progress (almost)
