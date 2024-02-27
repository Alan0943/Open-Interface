import time
from multiprocessing import Queue

from openai import OpenAIError

from interpreter import Interpreter
from llm import LLM


class Core:
    def __init__(self):
        self.status_queue = Queue()
        self.interrupt_execution = False

        self.interpreter = Interpreter(self.status_queue)
        try:
            self.llm = LLM()
        except OpenAIError as e:
            self.status_queue.put("Set your OpenAPI API Key in Settings and Restart the App")

    def execute_user_request(self, user_request):
        self.stop_previous_request()
        time.sleep(0.1)
        self.execute(user_request)

    def stop_previous_request(self):
        self.interrupt_execution = True

    def execute(self, user_request, step_num=0):
        """
            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already
                in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        self.interrupt_execution = False
        try:
            instructions = self.llm.get_instructions_for_objective(user_request, step_num)

            if instructions == {}:
                # Sometimes LLM sends malformed JSON response, in that case retry once more.
                instructions = self.llm.get_instructions_for_objective(user_request + " Please reply in valid JSON", step_num)

            for step in instructions["steps"]:
                if self.interrupt_execution:
                    self.status_queue.put("Interrupted")
                    self.interrupt_execution = False
                    return "Interrupted"
                else:
                    success = self.interpreter.process_command(step)

                    if not success:
                        return "Unable to execute the request"

        except Exception as e:
            self.status_queue.put(f"Exception Unable to execute the request - {e}")
            return f"Unable to execute the request - {e}"

        if instructions["done"]:
            # Communicate Results
            self.status_queue.put(instructions["done"])
            return instructions["done"]
        else:
            # if not done, continue to next phase
            self.status_queue.put("Fetching further instructions based on current state")
            return self.execute(user_request, step_num + 1)
