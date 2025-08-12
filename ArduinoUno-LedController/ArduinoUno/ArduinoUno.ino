#define ledRed 2
#define ledGreen 8

int mode = 0;
int interval = 500;
unsigned long prevMillis = 0;
bool ledState = false;

void setup() {
  pinMode(ledRed, OUTPUT);
  pinMode(ledGreen, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();

    switch (cmd) {
      case 'R': digitalWrite(ledRed, HIGH); break;
      case 'r': digitalWrite(ledRed, LOW); break;
      case 'G': digitalWrite(ledGreen, HIGH); break;
      case 'g': digitalWrite(ledGreen, LOW); break;


      case 'B': mode = 3; break;     // Blink mode
      case 'S': interval = 100; break;  // Speed up blink
      case 'D': interval = 500; break;  // Default blink
    }
  }

  // Blink Mode
  if (mode == 3) {
    unsigned long currentMillis = millis();
    if (currentMillis - prevMillis >= interval) {
      prevMillis = currentMillis;
      ledState = !ledState;
      digitalWrite(ledRed, ledState);
      digitalWrite(ledGreen, !ledState);
    }
  } else if (mode == 1) {
    digitalWrite(ledRed, HIGH);
    digitalWrite(ledGreen, LOW);
  } else if (mode == 2) {
    digitalWrite(ledGreen, HIGH);
    digitalWrite(ledRed, LOW);
  }
}
