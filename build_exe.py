

import PyInstaller.__main__
import shutil
from pathlib import Path
import os

APP_NAME = "PDF번역기_남광현_Test"
MAIN_SCRIPT = "gui/main_window.py"
ICON_FILE = "assets/icon.ico"
DIST_PATH = "dist"

def build_portable_exe():
    """
    PyInstaller를 사용하여 모든 의존성을 포함하는 포터블 EXE 파일을 생성합니다.
    BabelDOC 모듈, 데이터 파일, 숨겨진 import를 모두 처리합니다.
    """
    workpath = "build"
    specpath = "."
    
    # 이전 빌드 과정에서 생성된 불필요한 파일들을 정리합니다.
    if os.path.exists(DIST_PATH):
        shutil.rmtree(DIST_PATH)
    if os.path.exists(workpath):
        shutil.rmtree(workpath)
    if os.path.exists(f"{APP_NAME}.spec"):
        os.remove(f"{APP_NAME}.spec")

    print(f"PyInstaller로 '{APP_NAME}.exe' 빌드를 시작합니다...")

    # PyInstaller 명령어에 전달할 인수를 리스트로 구성합니다.
    pyinstaller_args = [
        '--name', APP_NAME,
        '--onefile', # 모든 것을 하나의 .exe 파일로 묶습니다.
        '--windowed',  # GUI 애플리케이션이므로 실행 시 검은 콘솔 창이 뜨지 않도록 합니다.
        '--icon', ICON_FILE,
        '--distpath', DIST_PATH,
        '--workpath', workpath,
        '--specpath', specpath,
        '--clean', # 빌드 전 이전 캐시를 정리합니다.
    ]

    # --- 데이터 파일 추가 ---
    # --add-data '원본경로;대상경로' 형식으로 .exe 파일 내에 포함될 파일을 지정합니다.
    pyinstaller_args.extend(['--add-data', 'BabelDOC/babeldoc/assets;babeldoc/assets'])
    pyinstaller_args.extend(['--add-data', 'config.json;.'])
    
    

    # --- 숨겨진 Import 추가 ---
    # PyInstaller가 정적 분석만으로는 찾아내지 못하는, 동적으로 로드되는 라이브러리들을 명시적으로 추가합니다.
    # 이 부분이 누락되면 .exe 실행 시 'ModuleNotFoundError' 오류가 발생할 수 있습니다.
    hidden_imports = [
        'google.generativeai', 'google.ai.generativelanguage', 'google.auth',
        'google_auth_oauthlib', 'google.api_core.bidi', 'google.api_core.client_options',
        'google.api_core.exceptions', 'google.api_core.future', 'google.api_core.gapic_v1',
        'google.api_core.grpc_helpers', 'google.api_core.path_template',
        'customtkinter', 'PIL', 'darkdetect',
        'flask', 'werkzeug', 'jinja2', 'itsdangerous', 'click',
        'keyring.backends.Windows', 'keyring.backends.SecretService', 'keyring.backends.macOS',
        'babeldoc', 're', 'pkg_resources'
    ]
    for imp in hidden_imports:
        pyinstaller_args.extend(['--hidden-import', imp])

    # 빌드할 메인 스크립트 파일
    pyinstaller_args.append(MAIN_SCRIPT)

    print(f"실행 인수: {' '.join(pyinstaller_args)}")

    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("\n" + "="*50)
        print(f"빌드가 성공적으로 완료되었습니다!")
        print(f"결과물은 '{os.path.abspath(DIST_PATH)}' 폴더에서 확인할 수 있습니다.")
        print("="*50)
    except Exception as e:
        print("\n" + "!"*50)
        print(f"빌드 중 오류가 발생했습니다: {e}")
        print("!"*50)

if __name__ == "__main__":
    if not os.path.exists(ICON_FILE):
        print(f"경고: 아이콘 파일({ICON_FILE})을 찾을 수 없습니다. 기본 아이콘으로 빌드됩니다.")
    build_portable_exe()
