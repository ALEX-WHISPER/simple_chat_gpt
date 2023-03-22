import os
import openai
import gradio as gr
import queue
import math
import hashlib
import json

OPEN_AI_KEY_NAME = "OPENAI_API_KEY"  # 环境变量名, 需要将 openai 平台提供的 key 添加到系统的环境变量中
OPEN_AI_APP_PWD_KEY = "OPENAI_APP_PWD_KEY"
system_desc = ""  # 性格设定
dialogue_records = queue.Queue()  # 历史记录, 用于支持上下文对话, 以队列形式组织, 队内元素超出上限则出队
dialogue_memory_size = 10  # 历史记录窗口的最大值
enable_context_support = True  # 是否开启上下文支持
temperature_value = 0.6
enable_authentication = True


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
        dialogue_records.empty()
    return enable_context_support


def on_role_changed(new_role):
    global system_desc
    system_desc = load_prompt_content(new_role)


def certify_auth(username, password):
    target_pwd = os.getenv(OPEN_AI_APP_PWD_KEY)
    encoded_pwd = hashlib.md5(password.encode()).hexdigest()

    if encoded_pwd == target_pwd:
        return True
    else:
        return False


def transcribe(audio_source):
    if audio_source is None:
        return ""
    else:
        audio_file = open(audio_source, "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"]


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

    return prompt_content


if __name__ == "__main__":
    # 读操作系统的环境变量, 本地调试前需要设置一下环境变量; 如果是部署到远端平台, 也可以在平台内设置
    api_key_name = os.getenv(OPEN_AI_KEY_NAME)

    if api_key_name is None:
        print("No such environment variable called: {}".format(OPEN_AI_KEY_NAME))
    else:
        # 设置 api key
        openai.api_key = api_key_name

        # 基于 gradio 设置 UI, 以及各元素交互后的回调
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

            choice_list = load_prompt_desc()
            role_radio = gr.Radio(choices=choice_list, label="Choose The Role", value=choice_list[0], type="index")
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

        # 启动
        if not enable_authentication:
            blocks.launch()
        else:
            blocks.launch(auth=certify_auth)
