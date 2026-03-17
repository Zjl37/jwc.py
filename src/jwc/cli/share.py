from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
from pathlib import Path
import socket
from urllib.parse import quote

import click

try:
    import ifaddr
except ImportError:
    ifaddr = None

try:
    import qrcode
except ImportError:
    qrcode = None


CAMPUS_NETWORK = ipaddress.ip_network("10.248.0.0/14")
DEFAULT_SHARE_PORT = 8000


def out_dir() -> Path:
    from .cache import jwc_cache_dir

    path = Path(jwc_cache_dir()) / "out"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_calendar_output_path(out_file: str | None, default_filename: str) -> Path:
    if out_file:
        return Path(out_file).expanduser()
    return out_dir() / default_filename


def write_calendar_file(path: str | Path, content: str) -> Path:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    resolved = output_path.resolve()
    click.echo(f"[i] 日历已写入 {resolved} 文件。")
    return resolved


def maybe_offer_http_share(path: str | Path) -> None:
    output_path = Path(path).expanduser().resolve()
    share_dir = out_dir().resolve()

    try:
        relative_path = output_path.relative_to(share_dir)
    except ValueError:
        # 当导出文件不在共享目录 share_dir 下，跳过局域网分享提示。
        return

    display_ip, ip_message = _pick_display_ip()

    if not click.confirm(
        "[?] 是否临时启动 HTTP 服务以共享 jwc-cache/out 目录，并展示该文件二维码？",
        default=("已优先使用校园网地址" in ip_message),
    ):
        return

    server = _create_http_server(share_dir)
    relative_url = quote(relative_path.as_posix(), safe="/")
    file_url = f"http://{display_ip}:{server.server_port}/{relative_url}"

    click.echo(f"[i] {ip_message}")
    click.echo(f"[i] 文件链接：{file_url}")
    _print_qr_code(file_url)
    click.secho("[i] 不再需要时，请及时按 ^C 关闭共享服务。", fg="yellow")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo()
        click.echo("[i] bye!")
    finally:
        server.server_close()


def _create_http_server(directory: Path) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))

    for port in range(DEFAULT_SHARE_PORT, DEFAULT_SHARE_PORT + 10):
        try:
            return ThreadingHTTPServer(("0.0.0.0", port), handler)
        except OSError:
            continue

    return ThreadingHTTPServer(("0.0.0.0", 0), handler)


def _pick_display_ip() -> tuple[str, str]:
    addresses = _discover_ipv4_addresses()
    if not addresses:
        return "127.0.0.1", "未发现可用的 IPv4 地址，二维码链接仅本机可访问。"

    campus_addresses = [
        address
        for address in addresses
        if ipaddress.ip_address(address) in CAMPUS_NETWORK
    ]
    if campus_addresses:
        return campus_addresses[0], f"已优先使用校园网地址 {campus_addresses[0]}"

    private_addresses = [
        address for address in addresses if ipaddress.ip_address(address).is_private
    ]
    if private_addresses:
        return private_addresses[
            0
        ], f"未发现校园网地址，改用私有地址 {private_addresses[0]}"

    return addresses[0], f"未发现校园网地址，改用 {addresses[0]}"


def _discover_ipv4_addresses() -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()

    if ifaddr is not None:
        for adapter in ifaddr.get_adapters():
            for ip_info in adapter.ips:
                ip_value = ip_info.ip
                if isinstance(ip_value, tuple):
                    continue
                if _is_usable_ipv4(ip_value) and ip_value not in seen:
                    seen.add(ip_value)
                    addresses.append(ip_value)

    for candidate in _default_route_candidates():
        if _is_usable_ipv4(candidate) and candidate not in seen:
            seen.add(candidate)
            addresses.append(candidate)

    return addresses


def _default_route_candidates() -> list[str]:
    candidates: list[str] = []
    for target in ("10.248.0.1", "223.5.5.5"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((target, 80))
                candidates.append(sock.getsockname()[0])
        except OSError:
            continue
    return candidates


def _is_usable_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return bool(
        address.version == 4
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_unspecified
    )


def _print_qr_code(url: str) -> None:
    click.echo("[i] 请用同网络下其他设备扫描下方二维码访问该文件：")

    if qrcode is None:
        click.secho("[!] 当前环境缺少 qrcode 依赖，无法展示二维码。", fg="yellow")
        return

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(tty=False, invert=True)
