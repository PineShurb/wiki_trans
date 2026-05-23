import json
import time
import sys
import urllib.request
import urllib.error
from translator_gateway import TranslatorGateway

def main():
    # 1. Load config
    with open('translator_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    ollama_cfg = config.get('ollama', {})
    provider = config.get('provider', 'local')
    model = ollama_cfg.get('model')
    host = ollama_cfg.get('host')
    timeout_val = float(ollama_cfg.get('timeout', 60))
    print(f"1) Config: Provider={provider}, Model={model}, Host={host}, Timeout={timeout_val}")

    # 2. Test connection
    print("2a) Connection test...")
    conn_ok = False
    conn_msg = ""
    try:
        url = f"{host.strip().rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status == 200:
                conn_ok = True
                conn_msg = "Success"
            else:
                conn_msg = f"Status {resp.status}"
    except Exception as e:
        conn_msg = str(e)
    print(f"Result: {'Success' if conn_ok else 'Failed'} - {conn_msg}")

    # 2b. Inference test (short)
    print("2b) Inference test (short)...")
    inf_ok = False
    inf_msg = ""
    try:
        # translate_ollama(host, model, text, timeout)
        res = TranslatorGateway.translate_ollama(host, model, "Hi", timeout=timeout_val)
        inf_ok = True
        inf_msg = res
    except Exception as e:
        inf_msg = str(e)
    print(f"Result: {'Success' if inf_ok else 'Failed'} - {inf_msg}")

    # 3. Extract prompt from log
    log_path = 'logs/trans_20260523_210030_654481.log'
    prompt = ""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            start_idx = -1
            for i, line in enumerate(lines):
                if "===== PROMPT SENT TO LLM =====" in line:
                    start_idx = i + 1
                    break
            if start_idx != -1:
                prompt_lines = []
                for line in lines[start_idx:]:
                    if line.startswith("====="):
                        break
                    prompt_lines.append(line)
                prompt = "".join(prompt_lines).strip()
    except Exception as e:
        print(f"Error reading log: {e}")

    char_count = len(prompt)
    line_count = len(prompt.splitlines())
    print(f"3) Extracted prompt: {char_count} chars, {line_count} lines")

    # 4. Large prompt test
    print(f"4) Testing large prompt with timeout {timeout_val}s...")
    start_time = time.time()
    success = False
    error_msg = ""
    try:
        # translate_ollama_stream(host, model, text, on_chunk, timeout)
        TranslatorGateway.translate_ollama_stream(host, model, prompt, lambda x: None, timeout=timeout_val)
        success = True
    except Exception as e:
        error_msg = str(e)
    end_time = time.time()
    duration = end_time - start_time
    print(f"Result: {'Success' if success else 'Failed'}, Time: {duration:.2f}s, Error: {error_msg}")

    # 5. Short prompt test if large one failed
    if not success:
        print(f"5) Testing short prompt to verify timeout setting...")
        start_time = time.time()
        success_short = False
        try:
            TranslatorGateway.translate_ollama_stream(host, model, "Hi", lambda x: None, timeout=timeout_val)
            success_short = True
        except Exception as e:
            print(f"Short prompt failed: {e}")
        end_time = time.time()
        print(f"Short prompt result: {'Success' if success_short else 'Failed'}, Time: {end_time - start_time:.2f}s")

if __name__ == "__main__":
    main()
