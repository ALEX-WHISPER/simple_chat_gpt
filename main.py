import openai
openai.api_key='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'

def use(prompt):
    response = openai.ChatCompletion.create\
    (
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    return response['choices'][0]['message']['content']

if __name__ == "__main__":
    r = use('晚上好')
    print(r)