# -*- coding: utf-8 -*-

import json
import base64
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.tts.v20190823 import tts_client, models
import yaml
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TTSSynthesizer:
    """
    腾讯云文本转语音(TTS)合成器类
    用于将文本转换为WAV格式的音频数据
    """
    
    # 音色列表
    YS_LIST = {
        601015: "爱小童 (男童声，大模型音色)",
        601000: "爱小溪 (聊天女声，大模型音色)",
        601001: "爱小洛 (阅读女声，大模型音色)",
        601002: "爱小辰 (聊天男声，大模型音色)",
        601003: "爱小荷 (阅读女声，大模型音色)",
        601004: "爱小树 (资讯男声，大模型音色)",
        601005: "爱小静 (聊天女声，大模型音色)",
        601006: "爱小耀 (阅读男声，大模型音色)",
        601007: "爱小叶 (聊天女声，大模型音色)",
        601008: "爱小豪 (聊天男声，大模型音色)",
        601009: "爱小芊 (聊天女声，大模型音色)",
        601010: "爱小娇 (聊天女声，大模型音色)"
    }
    
    # 情绪列表
    QX_LIST = {
        "neutral": "中性",
        "sad": "悲伤",
        "happy": "高兴",
        "angry": "生气",
        "fear": "恐惧",
        "news": "新闻",
        "story": "故事",
        "radio": "广播",
        "poetry": "诗歌",
        "call": "客服",
        "sajiao": "撒娇",
        "disgusted": "厌恶",
        "amaze": "震惊",
        "peaceful": "平静",
        "exciting": "兴奋",
        "aojiao": "傲娇",
        "jieshuo": "解说"
    }
    
    # 语速映射表
    SPEED_MAPPING = {
        -2: 0.6,
        -1: 0.8,
        0: 1.0,   # 默认
        1: 1.2,
        2: 1.5,
        6: 2.5
    }
    
    def __init__(self, config_path="config.yaml"):
        """初始化TTS合成器
        
        参数:
            config_path (str): 配置文件路径，默认为"config.yaml"
        """
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 腾讯云认证信息
        self.secret_id = self.config["txyun"]["secret_id"]
        self.secret_key = self.config["txyun"]["secret_key"]
        self.region = self.config["txyun"].get("region", "ap-beijing")
        
        # 初始化客户端
        self.client = self._init_client()
    
    def _load_config(self, config_path):
        """加载配置文件"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"加载配置文件失败: {e}")
    
    def _init_client(self):
        """初始化TTS客户端"""
        try:
            # 实例化认证对象
            cred = credential.Credential(self.secret_id, self.secret_key)
            
            # 配置HTTP选项
            http_profile = HttpProfile()
            http_profile.endpoint = "tts.tencentcloudapi.com"

            # 配置客户端选项
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            
            # 实例化TTS客户端
            return tts_client.TtsClient(cred, self.region, client_profile)
        except Exception as e:
            raise Exception(f"初始化TTS客户端失败: {e}")
    
    def _validate_params(self, voice_type, emotion, speed, volume):
        """验证参数有效性并返回修正后的值"""
        # 验证音色
        if voice_type not in self.YS_LIST:
            logging.warning(f"无效的音色类型，默认使用601000（爱小溪）")
            voice_type = 601000
            
        # 验证情绪
        if emotion not in self.QX_LIST:
            logging.warning(f"无效的情绪类型，默认使用neutral（中性）")
            emotion = "neutral"
            
        # 验证语速
        if speed not in self.SPEED_MAPPING:
            logging.warning(f"无效的语速值，默认使用0（1.0倍）")
            speed = 0
            
        # 验证音量
        if not (-10 <= volume <= 10):
            logging.warning(f"音量超出范围[-10,10]，默认使用0")
            volume = 0
            
        return voice_type, emotion, speed, volume
    
    def synthesize(self, txt, voice_type=601000, emotion="neutral", speed=0, volume=0):
        """
        将文本转换为语音数据
        
        参数:
            txt (str): 需要合成语音的文本内容
            voice_type (int): 音色类型，默认601000（爱小溪）
            emotion (str): 情绪类型，默认"neutral"（中性）
            speed (int): 语速，-2/(-1)/0/1/2/6，默认0（1.0倍）
            volume (float): 音量，范围[-10，10]，默认0（正常音量）
            
        返回:
            bytes: 成功返回WAV格式的音频数据(bytes)，失败返回None
        """
        try:
            # 验证参数有效性
            voice_type, emotion, speed, volume = self._validate_params(
                voice_type, emotion, speed, volume
            )

            # 转换语速值
            actual_speed = self.SPEED_MAPPING[speed]
            
            # 构造请求参数
            req = models.TextToVoiceRequest()
            params = {
                "Text": txt,
                "SessionId": "tts_synthesize_session",
                "Volume": volume,
                "Speed": actual_speed,
                "ProjectId": 0,
                "ModelType": 1,
                "VoiceType": voice_type,
                "PrimaryLanguage": 1,
                "SampleRate": 16000,
                "Codec": "wav",
                "SegmentRate": 1,
                "EmotionCategory": emotion,
                "EmotionIntensity": 100
            }
            req.from_json_string(json.dumps(params))

            # 调用API获取语音
            logging.info(f"正在合成语音: 音色={self.YS_LIST[voice_type]}, 情绪={self.QX_LIST[emotion]}, 语速={actual_speed}倍")
            resp = self.client.TextToVoice(req)
            response_data = json.loads(resp.to_json_string())
            
            # 解码Base64音频数据
            audio_data = base64.b64decode(response_data["Audio"])
            
            logging.info("语音合成成功")
            return audio_data

        except TencentCloudSDKException as err:
            logging.error(f"API调用错误: {err}")
        except Exception as e:
            logging.error(f"合成过程错误: {e}")
        return None
    
    def list_voices(self):
        """列出所有可用音色"""
        print("可用音色列表:")
        for code, name in self.YS_LIST.items():
            print(f"{code}: {name}")
    
    def list_emotions(self):
        """列出所有可用情绪"""
        print("\n可用情绪列表:")
        for code, name in self.QX_LIST.items():
            print(f"{code}: {name}")


if __name__ == "__main__":
    import os
    
    # 注意：请确保在同级目录下有一个config.yaml文件，内容如下:
    # txyun:
    #   secret_id: "YOUR_SECRET_ID"
    #   secret_key: "YOUR_SECRET_KEY"
    #   region: "ap-beijing"  # 可选, 默认为ap-beijing
    
    # 创建TTS合成器实例
    tts_synthesizer = TTSSynthesizer()
    
    # 列出所有可用选项
    tts_synthesizer.list_voices()
    tts_synthesizer.list_emotions()
    
    # --- 示例 1 ---
    print("\n===== 示例合成 1 =====")
    audio_data_1 = tts_synthesizer.synthesize("这是默认设置的合成示例，使用爱小溪的声音，中性情绪。")
    if audio_data_1:
        file_path_1 = "example_1.wav"
        with open(file_path_1, "wb") as f:
            f.write(audio_data_1)
        print(f"成功生成音频文件: {os.path.abspath(file_path_1)}")

    # --- 示例 2 ---
    print("\n===== 示例合成 2 =====")
    audio_data_2 = tts_synthesizer.synthesize("大家好，我是爱小童，我很高兴为大家播报新闻。", 
                                           voice_type=601015, 
                                           emotion="happy", 
                                           speed=1, 
                                           volume=2)
    if audio_data_2:
        file_path_2 = "example_2.wav"
        with open(file_path_2, "wb") as f:
            f.write(audio_data_2)
        print(f"成功生成音频文件: {os.path.abspath(file_path_2)}")

    # --- 示例 3 ---
    print("\n===== 示例合成 3 =====")
    audio_data_3 = tts_synthesizer.synthesize("这是一个带有悲伤情绪的示例，语速较慢。", 
                                           voice_type=601002, 
                                           emotion="sad", 
                                           speed=-1)
    if audio_data_3:
        file_path_3 = "example_3.wav"
        with open(file_path_3, "wb") as f:
            f.write(audio_data_3)
        print(f"成功生成音频文件: {os.path.abspath(file_path_3)}")