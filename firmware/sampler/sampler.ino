// Optional WATER sampler only. Incompatible with reeftrace_bench wiring.
// D9 -> Adafruit 5648 IN, Uno GND -> driver GND. External fused 12V -> driver.
// D2 -> local normally-closed enable contact -> GND. Open = disarmed.
#define ENABLE_SAMPLER 0
const byte PUMP=9, LOCAL_ENABLE=2;
char line[96]; byte used=0; bool overflow=false,armed=false,running=false;
char seen[16][33]; byte seenCount=0; char commandId[33]="";
unsigned long started=0,duration=0,lastContact=0,lastReport=0;
void off(const char* state) {
  digitalWrite(PUMP,LOW); running=false;
  Serial.print("{\"type\":\"sampler\",\"command_id\":\"");Serial.print(commandId);
  Serial.print("\",\"state\":\"");Serial.print(state);
  Serial.print("\",\"switched_ms\":");Serial.print(started ? millis()-started : 0);Serial.println("}");
}
void handle() {
  if(!strcmp(line,"STOP")) { off("stopped");armed=false;return; }
  if(!strcmp(line,"PING")) { lastContact=millis();return; }
  if(!strcmp(line,"ARM") && ENABLE_SAMPLER && digitalRead(LOCAL_ENABLE)==LOW && !running) {
    armed=true;lastContact=millis();Serial.println("{\"state\":\"armed\"}");return;
  }
  if(!strncmp(line,"PULSE ",6) && armed && !running && digitalRead(LOCAL_ENABLE)==LOW) {
    char *end;long ms=strtol(line+6,&end,10);
    if(end==line+6 || *end!=' ' || ms<1 || ms>5000) {Serial.println("{\"error\":\"duration\"}");return;}
    const char* id=end+1;byte len=strlen(id);
    if(len<1 || len>=33 || seenCount>=16) {Serial.println("{\"error\":\"id_or_session_full\"}");return;}
    for(byte i=0;i<len;i++) if(!isalnum(id[i]) && id[i]!='-' && id[i]!='_') {Serial.println("{\"error\":\"id\"}");return;}
    for(byte i=0;i<seenCount;i++) if(!strcmp(seen[i],id)) {Serial.println("{\"error\":\"duplicate\"}");return;}
    strcpy(seen[seenCount++],id);strcpy(commandId,id);
    duration=ms;started=lastContact=millis();running=true;digitalWrite(PUMP,HIGH);
    Serial.print("{\"state\":\"running\",\"command_id\":\"");Serial.print(id);Serial.println("\"}");return;
  }
  Serial.println("{\"error\":\"rejected\"}");
}
void setup() {
  digitalWrite(PUMP,LOW);pinMode(PUMP,OUTPUT);pinMode(LOCAL_ENABLE,INPUT_PULLUP);
  Serial.begin(115200);Serial.println("{\"boot\":\"reeftrace-sampler-v3\",\"state\":\"unarmed\"}");
}
void loop() {
  if(digitalRead(LOCAL_ENABLE)==HIGH || (armed && millis()-lastContact>2000)) {
    if(running) off("fault_local_enable_or_watchdog");armed=false;
  }
  if(running && millis()-started>=duration) off("completed");
  for(byte budget=0; Serial.available() && budget<96; budget++) {
    char c=Serial.read();
    if(c=='\n') {
      line[used]=0;if(!overflow)handle();else {off("fault_line_overflow");armed=false;}
      used=0;overflow=false;
    } else if(c!='\r') {
      if(used<sizeof(line)-1 && !overflow)line[used++]=c;else overflow=true;
    }
  }
}
