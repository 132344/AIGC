import yaml
import json
import logging
import wave
import os
import subprocess
from vosk import Model, KaldiRecognizer
from typing import Optional, Dict, Any, Callable

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VoskRecognizer:
    """基于Vosk的语音识别器，用于从音频数据中识别文本。"""
    
    def __init__(self, model_path: Optional[str] = None, config_path: str = "config.yaml"):
        """初始化语音识别器"""
        self.model: Optional[Model] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        
        # 加载配置和模型
        self.config: Dict[str, Any] = self._load_config(config_path)
        config_model_path: str = self.config.get("Vosk", {}).get("url", "")
        self.model_path: str = model_path if model_path is not None else config_model_path
        
        # 初始化模型
        self._initialize_model()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self._handle_error(f"配置文件加载失败: {e}")
            return {}
    
    def _initialize_model(self) -> bool:
        """初始化Vosk模型"""
        if not self.model_path:
            self._handle_error("未指定Vosk模型路径")
            return False
            
        try:
            self.model = Model(self.model_path)
            self._notify_status(f"Vosk模型加载成功: {self.model_path}")
            return True
        except Exception as e:
            self._handle_error(f"Vosk模型加载失败: {e}")
            self.model = None
            return False

    def _handle_error(self, message: str) -> None:
        """处理错误信息"""
        logging.error(message)
        if self.on_error:
            try:
                self.on_error(message)
            except Exception as e:
                logging.error(f"错误回调执行失败: {e}")
    
    def _notify_status(self, status: str) -> None:
        """通知状态变化"""
        logging.info(status)
        if self.on_status:
            try:
                self.on_status(status)
            except Exception as e:
                logging.error(f"状态回调执行失败: {e}")

    def recognize(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        if not self.model:
            self._handle_error("模型未加载，无法进行识别")
            return None

        temp_input_path = "asr_input_temp.webm"  # 假设为webm格式，但ffmpeg能自动检测格式
        temp_output_path = "asr_output_temp.wav"

        try:
            # 1. 将接收到的浏览器音频写入临时文件
            with open(temp_input_path, "wb") as f:
                f.write(audio_data)

            # 2. 使用ffmpeg转换为所需格式
            ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ffmpeg.exe')
            ffmpeg_command = [
                ffmpeg_path,
                "-y",
                "-i", temp_input_path,
                "-ac", "1",
                "-ar", "16000",
                "-acodec", "pcm_s16le",
                temp_output_path
            ]
            
            process = subprocess.run(ffmpeg_command, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if process.returncode != 0:
                self._handle_error(f"FFmpeg conversion failed: {process.stderr}")
                return None

            # 3. Read the converted, clean WAV file's PCM data
            with wave.open(temp_output_path, 'rb') as wf:
                pcm_data = wf.readframes(wf.getnframes())
                actual_rate = wf.getframerate()

            # 4. Pass the clean data to Vosk
            recognizer = KaldiRecognizer(self.model, actual_rate)
            recognizer.SetWords(True)
            recognizer.AcceptWaveform(pcm_data)
            
            result = json.loads(recognizer.FinalResult())
            recognized_text = result.get("text", "")
            
            self._notify_status(f"识别完成: {recognized_text}")
            return recognized_text

        except Exception as e:
            self._handle_error(f"语音识别过程出错: {e}")
            return None
        finally:
            # 5. Clean up temp files
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)


if __name__ == "__main__":
    import os
    import wave

    # --- 注意事项 ---
    # 1. 确保 `config.yaml` 文件存在并配置了Vosk模型路径:
    # Vosk:
    #   url: "path/to/your/vosk-model"
    # 2. 确保 `example_1.wav` 文件存在于同级目录 (可由 wzyy.py 生成)。

    # --- 回调函数示例 ---
    def handle_error(message: str):
        print(f"\n[回调] 错误: {message}")
    
    def handle_status(status: str):
        print(f"\n[回调] 状态: {status}")

    # --- 执行识别 ---
    audio_file_path = "example_1.wav"

    if not os.path.exists(audio_file_path):
        print(f"错误: 音频文件 '{audio_file_path}' 不存在。请先运行 wzyy.py 生成该文件。")
    else:
        # 创建识别器实例
        recognizer = VoskRecognizer()
        recognizer.on_error = handle_error
        recognizer.on_status = handle_status

        # 读取音频文件
        try:
            with wave.open(audio_file_path, "rb") as wf:
                # 验证音频格式是否符合Vosk要求
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    print("错误: 音频文件必须是单声道, 16-bit PCM, uncompressed WAV 格式。")
                else:
                    audio_data = wf.readframes(wf.getnframes())
                    sample_rate = wf.getframerate()
                    print(f"\n成功读取音频文件: {audio_file_path} (采样率: {sample_rate})")
                    
                    # 执行识别
                    text_result = recognizer.recognize(audio_data, sample_rate)
                    
                    if text_result is not None:
                        print("\n===== 识别结果 =====")
                        print(text_result)
                        print("======================\n")

        except Exception as e:
            print(f"处理音频文件时出错: {e}")