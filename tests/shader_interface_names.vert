#version 450
layout(location=0) in vec3 position;
// Blender's generated stage interfaces use ordinary struct variables. Tint
// must give their flattened entry-point fields new symbols, rather than
// reusing names still present on the private copies of these struct types.
struct A { vec3 prev; };
struct B { vec3 prev; vec4 position; };
layout(location=0) out A a;
layout(location=1) out B b;
void main() {
  gl_Position=vec4(position,1.0);
  a.prev=vec3(1,0,0);
  b.prev=vec3(0,1,0);
  b.position=vec4(0,0,1,1);
}
