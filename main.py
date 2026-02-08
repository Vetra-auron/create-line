import sys
import os
import argparse
from committee.member import CommitteeMember
from committee.chairperson import Chairperson

def main():
    parser = argparse.ArgumentParser(description="AI Committee Analysis Tool")
    parser.add_argument("file", nargs="?", help="File to analyze (optional)")
    args = parser.parse_args()

    content = ""
    if args.file:
        if os.path.exists(args.file):
            try:
                with open(args.file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading file: {e}")
                return
        else:
            print(f"Error: File '{args.file}' not found.")
            return
    else:
        print("Enter content to analyze (Press Ctrl+D on Linux/Mac or Ctrl+Z then Enter on Windows to finish):")
        try:
            content = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            return

    if not content.strip():
        print("Empty content. Exiting.")
        return

    print("\nProcessing content...")

    chair = Chairperson()

    # Initialize Members with distinct personas
    analyst = CommitteeMember(
        name="Analyst",
        role="Structural Analyst",
        persona_description="You are a meticulous analyst. Break down the content into key points and evaluate its logical flow and structure."
    )
    critic = CommitteeMember(
        name="Critic",
        role="Constructive Critic",
        persona_description="You are a critical thinker. Identify weaknesses, potential risks, logical fallacies, and missing information."
    )
    advisor = CommitteeMember(
        name="Advisor",
        role="Strategic Advisor",
        persona_description="You are a helpful advisor. Suggest concrete actionable steps to improve the content and maximize its impact."
    )

    chair.add_member(analyst)
    chair.add_member(critic)
    chair.add_member(advisor)

    results = chair.convene(content)
    final_report = chair.synthesize(results)

    print(final_report)

if __name__ == "__main__":
    main()
