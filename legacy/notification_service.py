"""Queue boundary; use RabbitMQ/Redis adapter in production."""
from queue import SimpleQueue
class NotificationQueue:
    def __init__(self): self.queue = SimpleQueue()
    def publish(self, event): self.queue.put(event)
    def drain(self):
        while not self.queue.empty(): yield self.queue.get()
notifications = NotificationQueue()
MESSAGES = {"en":"Confirmed animal-health outbreak within {radius} km. Follow LDO guidance.", "mr":"{radius} किमी परिसरात पशु आरोग्य उद्रेकाची पुष्टी झाली आहे. एलडीओच्या सूचनांचे पालन करा."}
def publish_priority_alert(case): notifications.publish({"type":"HIGH_TRIAGE", "case_id":case["id"], "district_code":case["district_code"], "priority":"immediate"})
def queue_outbreak_notifications(case_id, radius_km, language):
    language = language if language in MESSAGES else "en"; event = {"type":"OUTBREAK_CONFIRMED", "case_id":case_id, "radius_km":radius_km, "channels":["sms", "ivr"], "message":MESSAGES[language].format(radius=radius_km), "ivr_language":language}; notifications.publish(event); return {"queued":True, **event}
