import os
import openai
import gradio as gr
import queue
import math
import hashlib
import json

API_KEY_ENV_NAME = "OPENAI_API_KEY"  # 环境变量名, 需要将 openai 平台提供的 key 添加到系统的环境变量中
PWD_ENV_NAME = "OPENAI_APP_PWD_KEY"  # 环境变量名, 用于登录校验
system_index = 0
system_desc = ""  # 性格设定
dialogue_records = queue.Queue()  # 历史记录, 用于支持上下文对话, 以队列形式组织, 队内元素超出上限则出队
dialogue_memory_size = 10  # 历史记录窗口的最大值
enable_context_support = True  # 是否开启上下文支持
temperature_value = 0.6     # 调节回答的准确性/丰富性(越靠近0越准确, 越靠近1越丰富)
enable_authentication = False   # 是否启用登录校验


# 调用 open-ai 接口, 输入问题, 返回回答
def get_openai_response(input_msg):
    system_message = {"role": "system", "content": system_desc}
    user_message = {"role": "user", "content": input_msg}

    # system 设定在最前, 其次是历史记录, 最后是当前的用户输入
    message_list = [system_message]
    if enable_context_support:
        for dialogue in dialogue_records.queue:
            message_list.append(dialogue)
    message_list.append(user_message)

    for message_item in message_list:
        print(message_item)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=message_list,
        temperature=temperature_value
    )
    response_content = response["choices"][0]["message"]["content"]
    return response_content


def conversation_history(input_msg, history):
    history = history or []
    output_msg = get_openai_response(input_msg)

    dialogue_records.put({"role": "user", "content": input_msg})
    dialogue_records.put({"role": "assistant", "content": output_msg})

    # 当存储的对话记录数量超出窗口长度, 触发出队(连续2次, 包括指令与回答)
    if math.ceil(dialogue_records.qsize() / 2) > dialogue_memory_size:
        print("record size bigger than the maximum, pop the queue twice")
        dialogue_records.get()
        dialogue_records.get()

    print("current record size: {}, max size: {}".format(dialogue_records.qsize() / 2, dialogue_memory_size))

    history.append((input_msg, output_msg))

    return history, history


def on_personality_changed(description):
    global system_desc
    system_desc = description
    print("personality change to: {}".format(system_desc))


def on_memory_size_changed(new_size):
    global dialogue_memory_size
    new_size = int(new_size)
    dialogue_memory_size = max(2, min(new_size, 50))
    print("memory size change to: {}".format(dialogue_memory_size))


def on_temperature_changed(slider_num):
    global temperature_value
    temperature_value = min(max(0, slider_num), 1)
    print("temperature change to: {}".format(temperature_value))


def on_context_switch_changed(enable):
    global enable_context_support
    enable_context_support = enable
    if not enable:
        dialogue_records.queue.clear()
    return enable_context_support


def on_role_changed(new_role):
    print(f"current role index: {new_role}")

    global system_index
    system_index = min(max(0, new_role), get_prompts_num()-1)

    global system_desc
    system_desc = load_prompt_content(system_index)

    dialogue_records.queue.clear()
    print(f"dialogue records: {dialogue_records.qsize()}")


# 登录校验
def certify_auth(username, password):
    # 获取环境变量, 该值为正确密码经过md5算法加密后的字符串
    target_pwd = os.getenv(PWD_ENV_NAME)

    # 将输入的密码通过md5加密, 再转成16进制字符串
    encoded_pwd = hashlib.md5(password.encode()).hexdigest()

    # 二者相同, 则通过校验
    if encoded_pwd == target_pwd:
        return True
    else:
        print(f"correct md5: {encoded_pwd}, input md5: {target_pwd}")
        return False


# 调用 whisper-ai 接口, 将音频转化成文字
def transcribe(audio_source):
    if audio_source is None:
        return ""
    else:
        audio_file = open(audio_source, "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"]


# 读取 prompt 列表
def load_prompt_desc():
    desc_list = []

    f = open("prompts.json")
    data = json.load(f)
    for item in data['sys_prompts']:
        desc_list.append(item['des'])
    f.close()

    if len(desc_list) == 0:
        desc_list.append("assistant")

    return desc_list


# 读取指定的 prompt 内容
def load_prompt_content(index):
    prompt_content = ""

    f = open("prompts.json")
    data = json.load(f)
    for item in data['sys_prompts']:
        if str(item['index']) == str(index):
            prompt_content = item['content']
    f.close()

    if len(prompt_content) == 0:
        print(f"ERROR: prompt content with index '{index}' not found!")
        prompt_content = "You are a kind and helpful assistant"

    print(f"content: {prompt_content}")
    return prompt_content


def get_prompts_num():
    f = open("prompts.json")
    data = json.load(f)
    return len(data['sys_prompts'])


# 检查并设置 api key
def check_open_ai_key():
    # 读操作系统的环境变量, 本地调试前需要设置一下环境变量; 如果是部署到远端平台, 也可以在平台内设置
    api_key = os.getenv(API_KEY_ENV_NAME)
    if api_key is None:
        print("Such environment variable NOT found: {}".format(API_KEY_ENV_NAME))
        return False
    else:
        openai.api_key = api_key
        return True


# 重置
def on_click_reset():
    on_role_changed(0)
    return "Default"


# 创建UI界面
def build_interface():
    blocks = gr.Blocks()
    with blocks:
        # personality = gr.Textbox(label="personality", placeholder="Describe the way you want your assistant to act like", value=personality_des)
        # personality.change(on_personality_changed, inputs=[personality], outputs=[])

        # context_switch = gr.Checkbox(label="context switch", info="Enable context-based dialogue", value=enable_context_support)
        # context_switch.change(on_context_switch_changed, inputs=[context_switch], outputs=[])

        # memory_size = gr.Number(label="Memory Size", value=dialogue_memory_size)
        # memory_size.change(on_memory_size_changed, inputs=[memory_size], outputs=[])

        # temperature_slider = gr.Slider(0, 1, step=0.1, label="temperature")
        # temperature_slider.change(on_temperature_changed, inputs=[temperature_slider], outputs=[])

        # choose the role
        choice_list = load_prompt_desc()
        role_radio = gr.Radio(choices=choice_list, label="Choose The Role", value=choice_list[system_index], type="index")
        role_radio.change(on_role_changed, inputs=[role_radio], outputs=[])

        # talking area
        chatbot = gr.Chatbot(label="Chatting Window")

        # text input area
        message = gr.Textbox(label="Text Input", placeholder="Enter your message...")

        # audio input area
        audio_input = gr.Audio(source="microphone", label="Audio Input", type="filepath")
        audio_input.change(transcribe, inputs=[audio_input], outputs=[message])

        # submit button
        submit = gr.Button("Send")
        state = gr.State()
        submit.click(conversation_history, inputs=[message, state], outputs=[chatbot, state])

        # reset button
        reset_btn = gr.Button("Reset")
        reset_btn.click(on_click_reset, inputs=[], outputs=[role_radio])

    # 启动
    if not enable_authentication:
        blocks.launch()
    else:
        blocks.launch(auth=certify_auth)


if __name__ == "__main__":
    if check_open_ai_key():
        build_interface()
    else:
        print("Interface init failed due to api key issue")
