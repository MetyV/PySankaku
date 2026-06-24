![AI-assisted](https://img.shields.io/badge/AI--assisted-all-blue)

Code's shit, idgaf, flow state did it. Improvements? Eventually. Maybe. If the ADHD gods bless me again.

TODO:
1. Write readme -> OK
2. More todo -> Fail
4. AI readme -> 50%
5. Post post (https://sankakuapi.com/posts POST Authorization)
5.1
data = {
    "post[parent_id]": "",
    "post[rating]": "e", # Chtob ne banili. mojno i 's'
    "post[tags]": '[]',
    "post[upload_url]": "",
    "post[pool_id]": "",
    "post[reupload_post_id]": ""
}
files = {
    "post[file]": (
        "123.jpg",
        open("123.jpg", "rb"),
        "image/jpeg"  # MIME
    )
}
response = requests.post(url, data=data, files=files)
   
In progress (almost)
