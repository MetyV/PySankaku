import json
from pathlib import Path

class accounts:
    def __init__(self) -> None:
        self.accF = Path('accounts.json')

    async def addAcc(self, login: str | None = None, password: str | None = None, mail: str | None = None):
        if self.accF.exists():
            with open(self.accF, 'r') as f:
                accounts = json.load(f)
            next_id = max((int(key) for key in accounts.keys()), default=0) + 1
        else:
            accounts = {}
            next_id = 1

        accounts[str(next_id)] = {
            'mail': mail,
            'login': login,
            'password': password
        }

        with open(self.accF, 'w') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)

    async def getAcc(self, all = False, login: str = '', mail: str = '') -> dict:
        if not self.accF.exists():
            return {}

        with open(self.accF, 'r') as f:
            data = json.load(f)
            data = {str(i): acc for i, acc in enumerate(data, 1)} if isinstance(data, list) else data

            if all:
                return data
            
            for acc_id, acc_data in data.items():
                acc_login = acc_data.get('login', '')
                acc_mail = acc_data.get('mail', '')
                
                if (login and (acc_login == login or acc_mail == login)) or \
                (mail and acc_mail == mail):
                    return {acc_id: acc_data}
        return {}