
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from flask import Flask, request, jsonify
import threading
import time
import logging
import socket
from typing import Tuple

# 로깅 기본 설정: 문제 발생 시 원인 추적을 위한 상세 로그를 기록합니다.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [GeminiBridge] - %(message)s', encoding='utf-8')

class GeminiOpenAIBridge:
    """
    Gemini API를 OpenAI ChatCompletion API와 호환되는 로컬 서버로 래핑합니다.
    QPS 제한, 상세 오류 처리 기능이 포함되어 있습니다.
    """
    def __init__(self, api_key: str, model: str, qps: float):
        self.api_key = api_key
        self.model = model
        self.qps = qps
        self.last_request_time = 0
        self.logger = logging.getLogger(__name__)

        try:
            # Google Gemini 클라이언트를 초기화합니다.
            # genai.configure(api_key=self.api_key) # 환경 변수를 통해 API 키를 로드합니다.
            self.client = genai.GenerativeModel(self.model)
            self.logger.info(f"Gemini 클라이언트가 '{self.model}' 모델로 성공적으로 초기화되었습니다.")
        except Exception as e:
            self.logger.error(f"Gemini 클라이언트 초기화 실패: {e}")
            raise

        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        """OpenAI 호환 API 엔드포인트를 설정합니다. BabelDOC은 이 주소로 요청을 보냅니다."""
        @self.app.route('/v1/chat/completions', methods=['POST'])
        def chat_completions():
            return self.handle_chat_completions()

    def handle_chat_completions(self):
        """OpenAI ChatCompletion API 요청을 처리하고 Gemini API로 변환하여 응답합니다."""
        try:
            # API 과다 사용을 방지하기 위해 QPS 제한을 먼저 적용합니다.
            self.apply_rate_limit()

            data = request.json
            messages = data.get('messages', [])
            
            # BabelDOC이 보낸 메시지 목록에서 실제 번역할 내용을 추출합니다.
            user_message = ""
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
            
            if not user_message:
                self.logger.warning("요청에서 사용자 메시지를 찾을 수 없습니다.")
                return jsonify({"error": "No user message found"}), 400

            self.logger.info(f"'{self.model}' 모델로 번역 요청을 보냅니다. (내용 일부: {user_message[:50]}...)")
            
            # Gemini API 호출 및 발생 가능한 오류들을 상세하게 처리합니다.
            try:
                response = self.client.generate_content(user_message)
                translated_text = response.text
                
                # Gemini 응답을 BabelDOC이 이해할 수 있는 OpenAI 형식으로 변환합니다.
                openai_response = self.format_as_openai_response(translated_text, user_message)
                self.logger.info("번역 성공. OpenAI 형식으로 응답을 반환합니다.")
                return jsonify(openai_response)

            # API 키가 잘못되었을 경우
            except google_exceptions.PermissionDenied as e:
                self.logger.error(f"Gemini API 권한 오류: {e}")
                return jsonify({"error": {"message": "잘못된 Gemini API 키입니다. 키를 확인해주세요.", "type": "invalid_request_error", "code": "invalid_api_key"}}), 401
            # API 사용량 한도를 초과했을 경우
            except google_exceptions.ResourceExhausted as e:
                self.logger.error(f"Gemini API 할당량 초과: {e}")
                return jsonify({"error": {"message": "API 할당량을 초과했습니다. 잠시 후 다시 시도하거나 Google Cloud 콘솔에서 할당량을 확인하세요.", "type": "insufficient_quota", "code": "quota_exceeded"}}), 429
            # 그 외 모든 Gemini API 관련 오류
            except Exception as e:
                self.logger.error(f"Gemini API 호출 중 알 수 없는 오류 발생: {e}")
                return jsonify({"error": {"message": f"번역 실패: {str(e)}", "type": "api_error"}}), 500

        # 요청 처리 과정 자체에서 발생한 오류
        except Exception as e:
            self.logger.error(f"요청 처리 중 내부 오류 발생: {e}")
            return jsonify({"error": {"message": f"Request processing failed: {str(e)}", "type": "internal_error"}}), 500

    def apply_rate_limit(self):
        """QPS(초당 요청 수) 제한을 적용하여 API 서버에 과도한 부하를 주지 않도록 합니다."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.qps if self.qps > 0 else 0
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            self.logger.info(f"QPS 제한({self.qps}/s)을 위해 {sleep_time:.2f}초 대기합니다.")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def format_as_openai_response(self, translated_text: str, original_text: str) -> dict:
        """Gemini 응답을 OpenAI ChatCompletion 응답 형식으로 변환합니다."""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": translated_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(original_text.split()),
                "completion_tokens": len(translated_text.split()),
                "total_tokens": len(original_text.split()) + len(translated_text.split())
            }
        }

    def start_server(self, host: str, port: int):
        """Flask 서버를 시작합니다."""
        self.logger.info(f"Gemini-OpenAI 브릿지 서버를 {host}:{port}에서 시작합니다.")
        # Werkzeug의 기본 로거 비활성화하여 GUI 로그창에 중복 로그가 찍히는 것을 방지합니다.
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        self.app.run(host=host, port=port, debug=False, threaded=True)

def find_free_port() -> int:
    """다른 프로그램과 충돌하지 않도록 사용 가능한 포트를 동적으로 찾습니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def start_gemini_bridge(api_key: str, model: str, qps: float) -> Tuple[str, int]:
    """
    백그라운드 스레드에서 Gemini 브릿지 서버를 시작하고,
    서버의 base_url과 포트 번호를 반환합니다.
    """
    port = find_free_port()
    host = '127.0.0.1'
    
    try:
        bridge = GeminiOpenAIBridge(api_key, model, qps)
        server_thread = threading.Thread(
            target=bridge.start_server, 
            args=(host, port),
            daemon=True # 메인 프로그램이 종료되면 이 스레드도 자동으로 종료됩니다.
        )
        server_thread.start()
        time.sleep(2) # 서버가 완전히 시작될 때까지 잠시 대기합니다.
        
        base_url = f"http://{host}:{port}"
        logging.info(f"브릿지 서버가 {base_url} 에서 성공적으로 시작되었습니다.")
        return base_url, port
    except Exception as e:
        logging.error(f"브릿지 서버 시작에 실패했습니다: {e}")
        raise
