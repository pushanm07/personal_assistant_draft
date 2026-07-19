def should_search(question):

    prompt = f"""
You are deciding if a web search is required.

Return ONLY YES or NO.

Question:

{question}
"""

    result = llm.generate(prompt)

    return "YES" in result.upper()