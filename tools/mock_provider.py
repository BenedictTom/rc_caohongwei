"""本地 mock provider：把 POST/PUT/PATCH body 原样回写为 200 JSON。

用途：让 providers.yaml 的 demo-* url 都能接通，dispatcher 拿到 200 → SUCCEEDED。
随机引入少量 5xx/超时让 dashboard 有"非全绿"的样本。

启动：python tools/mock_provider.py [--port 8500] [--fail-rate 0.0]
"""
import argparse
import json
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    fail_rate: float = 0.0

    def _read_body(self) -> str:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8", errors="replace") if n else ""

    def _handle(self) -> None:
        body = self._read_body()
        # 故意在一小部分请求上模拟上游异常，便于看到 dashboard 的失败/重试样本。
        if self.fail_rate > 0 and random.random() < self.fail_rate:
            mode = random.choice(("500", "timeout"))
            if mode == "timeout":
                time.sleep(6)  # 超过任何 provider 的 timeout_ms，触发客户端超时
                return
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":false,"err":"mock 5xx"}')
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "echoed": body}).encode("utf-8"))

    do_POST = _handle  # type: ignore[assignment]
    do_PUT = _handle  # type: ignore[assignment]
    do_PATCH = _handle  # type: ignore[assignment]

    def log_message(self, *_a, **_kw) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8500)
    parser.add_argument("--fail-rate", type=float, default=0.0,
                        help="0~1 之间，触发模拟 500 / 超时的比例")
    args = parser.parse_args()

    _Handler.fail_rate = args.fail_rate
    print(f"mock provider listening on 127.0.0.1:{args.port} (fail_rate={args.fail_rate})")
    HTTPServer(("127.0.0.1", args.port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
