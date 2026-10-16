// Uno dry-bench controller. No pump or gantry control.
#include <Servo.h>
#include <LiquidCrystal.h>
#define USE_LCD 0
#define ENABLE_SERVOS 0 // Enable only after separate regulated 5V power is wired.
const byte TRIG=7, ECHO=8, PAN=9, TILT=10, STOP_PIN=2;
Servo panServo, tiltServo;
LiquidCrystal lcd(12,11,6,5,4,3);
char input[48]; byte used=0; bool overflow=false, armed=false;
unsigned long lastContact=0, lastSample=0;
int panAngle=90, tiltAngle=90;
void stopMotion() {
  armed=false; panServo.detach(); tiltServo.detach();
  // Detach stops pulses, NOT power. Physical stop must interrupt servo power.
}
void reply(const char* message) { Serial.println(message); }
void command() {
  if (!strcmp(input,"STOP")) { stopMotion(); reply("{\"ack\":\"STOP\"}"); }
  else if (!strcmp(input,"PING")) { lastContact=millis(); reply("{\"ack\":\"PING\"}"); }
  else if (!strcmp(input,"ARM") && ENABLE_SERVOS && digitalRead(STOP_PIN)==LOW) {
    panAngle=tiltAngle=90;
    panServo.write(90); tiltServo.write(90);
    panServo.attach(PAN); tiltServo.attach(TILT);
    lastContact=millis(); armed=true; reply("{\"ack\":\"ARM\"}");
  } else {
    char *endPan, *endTilt;
    bool posePrefix = strncmp(input,"POSE ",5)==0;
    long p = posePrefix ? strtol(input+5, &endPan, 10) : 0;
    long t = 0;
    bool validPose = posePrefix && endPan != input+5 && *endPan == ' ';
    if (validPose) {
      t = strtol(endPan+1, &endTilt, 10);
      validPose = endTilt != endPan+1 && *endTilt == 0;
    }
    if (validPose && armed &&
        digitalRead(STOP_PIN)==LOW && p>=30 && p<=150 && t>=60 && t<=120) {
      panAngle=p; tiltAngle=t; panServo.write(p); tiltServo.write(t);
      lastContact=millis(); reply("{\"ack\":\"POSE\"}");
    } else reply("{\"error\":\"rejected\"}");
  }
}
void setup() {
  pinMode(TRIG,OUTPUT); digitalWrite(TRIG,LOW); pinMode(ECHO,INPUT);
  pinMode(STOP_PIN,INPUT_PULLUP); Serial.begin(115200); stopMotion();
  if (USE_LCD) { lcd.begin(16,2); lcd.print("ReefTrace bench"); }
  reply("{\"boot\":\"reeftrace-bench-v1\"}");
}
void loop() {
  if (digitalRead(STOP_PIN)==HIGH || (armed && millis()-lastContact>2000)) stopMotion();
  while (Serial.available()) {
    char c=Serial.read();
    if(c=='\n') {
      input[used]=0; if(!overflow) command(); else reply("{\"error\":\"line_too_long\"}");
      used=0; overflow=false;
    } else if(c!='\r') {
      if(used<sizeof(input)-1 && !overflow) input[used++]=c; else overflow=true;
    }
  }
  if(millis()-lastSample>=250) {
    lastSample=millis();
    digitalWrite(TRIG,HIGH); delayMicroseconds(10); digitalWrite(TRIG,LOW);
    unsigned long duration=pulseIn(ECHO,HIGH,25000UL);
    float distance=duration*0.0343f/2;
    Serial.print("{\"type\":\"telemetry\",\"uptime_ms\":"); Serial.print(millis());
    Serial.print(",\"distance_cm\":");
    if(duration && distance>=2 && distance<=400) Serial.print(distance,1); else Serial.print("null");
    Serial.print(",\"pot_raw\":"); Serial.print(analogRead(A0));
    Serial.print(",\"armed\":"); Serial.print(armed ? "true":"false");
    Serial.print(",\"pan_deg\":"); Serial.print(panAngle);
    Serial.print(",\"tilt_deg\":"); Serial.print(tiltAngle); Serial.println("}");
    if(USE_LCD) {
      lcd.setCursor(0,1); lcd.print("                "); lcd.setCursor(0,1);
      lcd.print(armed ? "ARM " : "SAFE ");
      if(duration) { lcd.print(distance,1); lcd.print("cm"); } else lcd.print("No echo");
    }
  }
}
