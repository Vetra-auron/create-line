import os

# Try to import OpenAI, handle if not installed
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class CommitteeMember:
    def __init__(self, name, role, persona_description, api_key=None):
        """
        Initialize a committee member.

        Args:
            name (str): The name of the member (e.g., "Alice").
            role (str): The role of the member (e.g., "Critic").
            persona_description (str): A description of how the member should behave.
            api_key (str, optional): OpenAI API key. Defaults to environment variable.
        """
        self.name = name
        self.role = role
        self.persona_description = persona_description

        # Check for API key
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if key and OpenAI:
            self.client = OpenAI(api_key=key)
        else:
            self.client = None

    def analyze(self, content):
        """
        Analyzes the content based on the member's persona.

        Args:
            content (str): The text content to analyze.

        Returns:
            str: The analysis result.
        """
        if self.client:
            try:
                system_prompt = (
                    f"You are {self.name}, acting as a {self.role}.\n"
                    f"Persona: {self.persona_description}\n"
                    "Provide your analysis in a helpful and constructive manner.\n"
                    "IMPORTANT: Respond in the same language as the input content."
                )

                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Using a cost-effective model
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Here is the content to analyze:\n\n{content}"}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"[Error calling API for {self.name}: {str(e)}]"
        else:
            # Mock response for demonstration when no API key is present
            return (
                f"--- [{self.name} ({self.role}) Analysis (MOCK)] ---\n"
                f"Based on my perspective as a {self.role}, I see that you wrote about: '{content[:30]}...'\n\n"
                f"Feedback (Simulated based on persona: {self.persona_description}):\n"
                "1. This is a solid starting point.\n"
                "2. Consider expanding on the key themes.\n"
                "3. [Note: Set OPENAI_API_KEY environment variable for real AI analysis.]"
            )
