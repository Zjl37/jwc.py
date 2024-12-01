import requests
from bs4 import BeautifulSoup as bs

def goto_bind_auth():
    bind_auth_req = requests.Request('GET', 'https://ids.hit.edu.cn/authserver/login?service=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin')
    return bind_auth_req

def goto_sz_auth(response_content):
    soup = bs(response_content, 'html.parser')
    try:
        sz_login_url = "https://ids.hit.edu.cn" + soup.select_one("body > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > section > div:nth-of-type(2) > div > div > span:nth-of-type(2) > a")['href'] + "&success=http%3A%2F%2Fjw.hitsz.edu.cn%2FcasLogin"
        sz_login_url = sz_login_url.replace("amp;", "")
    except:
        raise Exception("获取登录地址失败")
    
    jump_to_login_request = requests.Request('GET', sz_login_url)
    return jump_to_login_request

def generate_login_form(soup, username, password):
    try:
        redirect_url = soup.select_one("#authZForm > input:nth-of-type(3)")['value']
        client_id = soup.select_one("#authZForm > input:nth-of-type(4)")['value']
        state = soup.select_one("#authZForm > input:nth-of-type(6)")['value']
        form = {
            "action": "authorize",
            "response_type": "code",
            "redirect_uri": redirect_url,
            "client_id": client_id,
            "scope": "",
            "state": state,
            "username": username,
            "password": password,
        }
        return form
    except:
        raise Exception("生成登录表单失败")

def login_request(response_content, username, password):
    soup = bs(response_content, 'html.parser')
    try:
        login_url = "https://sso.hitsz.edu.cn:7002" + soup.select_one("#authZForm")['action']
    except:
        raise Exception("获取登录地址失败")
    login_request = requests.Request('POST', login_url, data=generate_login_form(soup, username, password))
    return login_request

def auth_ticket(ticket_url):
    auth_ticket_request = requests.Request('GET', ticket_url)
    return auth_ticket_request

def auth_login(session:requests.session, username:str, password:str):
    try:
        bind_auth_req = goto_bind_auth()
        bind_auth_res = session.send(bind_auth_req.prepare())
        
        if bind_auth_res.status_code != 200:
            return False, "访问联合认证失败"
        
        goto_sz_req = goto_sz_auth(bind_auth_res.text)
        goto_sz_res = session.send(goto_sz_req.prepare())
        
        if goto_sz_res.status_code != 200:
            return False, "跳转至深圳登录界面失败"
        
        login_req = login_request(goto_sz_res.text,username, password)
        login_res = session.send(login_req.prepare())
        
        if login_res.status_code != 200:
            return False, "登录请求失败。请检查账号密码是否正确"
        
        if "/authentication/main" not in login_res.url:
            return False, "登录失败。请检查账号密码是否正确"
        
        return True, "登录成功"
    
    except Exception as e:
        return False, str(e)
    
if __name__ == "__main__":
    session = requests.Session()
    # proxy = {
    #     "http": "http://127.0.0.1:7723",
    #     "https": "http://127.0.0.1:7723"
    # }
    username = input("请输入账号：")
    password = input("请输入密码：")
    #print(auth_login(session, username, password,proxy))
    print(auth_login(session, username, password))