class Ownership(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)

class invalidVoiceChannel(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)