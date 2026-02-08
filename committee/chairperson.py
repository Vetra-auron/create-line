from .member import CommitteeMember

class Chairperson:
    def __init__(self):
        """Initialize the Chairperson with an empty list of members."""
        self.members = []

    def add_member(self, member: CommitteeMember):
        """
        Add a member to the committee.

        Args:
            member (CommitteeMember): The member to add.
        """
        self.members.append(member)

    def convene(self, content: str):
        """
        Asks all members to analyze the content.

        Args:
            content (str): The text content to be analyzed.

        Returns:
            dict: A dictionary mapping member names to their analysis.
        """
        results = {}
        # Using simple print for CLI feedback, could be logging
        print(f"--- Chairperson: Convening committee for analysis... ---")
        for member in self.members:
            print(f"Asking {member.name} ({member.role})...")
            analysis = member.analyze(content)
            results[member.name] = analysis
        return results

    def synthesize(self, results: dict):
        """
        Synthesizes the results into a final report string.

        Args:
            results (dict): The dictionary of analyses from `convene`.

        Returns:
            str: The formatted report.
        """
        report = "\n================ COMMITTEE REPORT ================\n\n"
        for name, analysis in results.items():
            report += f"### {name}'s Feedback:\n{analysis}\n\n"
            report += "-" * 50 + "\n\n"

        report += "================ END OF REPORT ================"
        return report
