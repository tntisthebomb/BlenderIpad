#version 450
layout(location=0) in vec3 position;
layout(location=0) out A { vec3 prev; } a;
layout(location=1) out B { vec3 prev; vec4 position; } b;
void main() {
  gl_Position=vec4(position,1.0);
  a.prev=vec3(1,0,0);
  b.prev=vec3(0,1,0);
  b.position=vec4(0,0,1,1);
}
