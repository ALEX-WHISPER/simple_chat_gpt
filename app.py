import os
import openai
import gradio as gr
import configobj

OPEN_AI_KEY_NAME = "OPENAI_API_KEY"  # 环境变量名, 需要将 openai 平台提供的 key 添加到系统的环境变量中
personality_des = "你是一个热心友好的助手"  # 性格设定
dialogue_records = []  # 历史记录, 用于支持上下文对话
max_round = 10  # 历史记录的最大值, 限制 token 的消耗
enable_context_support = False  # 是否开启上下文支持
temperature_value = 0.6


def get_openai_response(input_msg):
    system_message = {"role": "system", "content": personality_des}
    user_message = {"role": "user", "content": input_msg}

    # system 设定在最前, 其次是历史记录, 最后是当前的用户输入
    message_list = [system_message]
    if enable_context_support:
        for dialogue in dialogue_records:
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

    # 使对话支持上下文, 但 token 的消耗量也会随之叠加, 因此设置一个回合上限, 对话数量超出上限则清空历史记录
    if len(dialogue_records) * 2 > max_round:
        dialogue_records.clear()
    else:
        dialogue_records.append({"role": "user", "content": input_msg})
        dialogue_records.append({"role": "assistant", "content": output_msg})

    history.append((input_msg, output_msg))

    return history, history


def on_personality_changed(description):
    global personality_des
    personality_des = description
    print("personality change to: {}".format(personality_des))


def on_temperature_changed(slider_num):
    global temperature_value
    temperature_value = min(max(0, slider_num), 1)
    print("temperature change to: {}".format(temperature_value))


def on_context_switch_changed(enable):
    global enable_context_support
    enable_context_support = enable
    if not enable:
        dialogue_records.clear()
    return enable_context_support


if __name__ == "__main__":
    # 先找环境变量, 下面列出2种方法
    # 方法1: 读工程内的配置文件, 方便但不安全
    # config = configobj.ConfigObj('.env')
    # api_key_name = config[OPEN_AI_KEY_NAME]

    # 方法2: 读操作系统的环境变量, 本地调试前需要设置一下环境变量; 如果是部署到远端平台, 也可以在平台内设置
    api_key_name = os.getenv(OPEN_AI_KEY_NAME)

    if api_key_name is not None:
        # 设置 api key
        openai.api_key = api_key_name

        # 基于 gradio 设置 UI
        blocks = gr.Blocks()
        with blocks:
            personality = gr.Textbox(label="personality", placeholder="Describe the way you want your assistant to act like", value=personality_des)
            personality.change(on_personality_changed, inputs=[personality], outputs=[])

            context_switch = gr.Checkbox(label="context switch", info="Enable context-based dialogue", value=enable_context_support)
            context_switch.change(on_context_switch_changed, inputs=[context_switch], outputs=[])

            temperature_slider = gr.Slider(0, 1, step=0.1, label="temperature")
            temperature_slider.change(on_temperature_changed, inputs=[temperature_slider], outputs=[])

            chatbot = gr.Chatbot(label="Chatting Window")

            message = gr.Textbox(label="input message", placeholder="Enter your message...")
            submit = gr.Button("Send")
            state = gr.State()
            submit.click(conversation_history, inputs=[message, state], outputs=[chatbot, state])

        # 启动
        blocks.launch()
    else:
        print("No such environment variable called: {}".format(OPEN_AI_KEY_NAME))
