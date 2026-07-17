"""
AURORA AI CIO v3.1

L9 Learning Engine

L9.4 Knowledge Base Engine v1.0

Purpose:
Convert past investment experience
into reusable knowledge.

Tracks:
- Successful Patterns
- Failed Patterns
- Market Conditions
- Investment Rules

Output:
AI Knowledge Base
"""


from datetime import datetime



class KnowledgeBaseEngine:


    def __init__(self):

        self.status = "ACTIVE"

        self.knowledge = {

            "success_patterns": [],

            "failure_patterns": [],

            "market_conditions": [],

            "investment_rules": []

        }





    def store_success_pattern(
        self,
        pattern
    ):


        self.knowledge["success_patterns"].append(

            {

                "pattern":

                pattern,

                "timestamp":

                datetime.utcnow().isoformat()

            }

        )


        return "SUCCESS_PATTERN_STORED"





    def store_failure_pattern(
        self,
        pattern
    ):


        self.knowledge["failure_patterns"].append(

            {

                "pattern":

                pattern,

                "timestamp":

                datetime.utcnow().isoformat()

            }

        )


        return "FAILURE_PATTERN_STORED"





    def store_market_condition(
        self,
        condition
    ):


        self.knowledge["market_conditions"].append(

            {

                "condition":

                condition,

                "timestamp":

                datetime.utcnow().isoformat()

            }

        )


        return "MARKET_CONDITION_STORED"





    def create_investment_rule(
        self,
        rule
    ):


        self.knowledge["investment_rules"].append(

            {

                "rule":

                rule,

                "timestamp":

                datetime.utcnow().isoformat()

            }

        )


        return "INVESTMENT_RULE_CREATED"





    def search_knowledge(
        self,
        keyword
    ):


        results = []


        for category in self.knowledge:


            for item in self.knowledge[category]:


                if keyword.lower() in str(item).lower():

                    results.append(item)



        return results





    def generate_knowledge_report(
        self
    ):


        return {


            "engine":

            "L9.4 Knowledge Base Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "knowledge":

            self.knowledge

        }
