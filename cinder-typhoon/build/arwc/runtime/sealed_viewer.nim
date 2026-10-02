import os, json

proc u16(data: string, offset: int): uint16 =
  uint16(ord(data[offset])) or (uint16(ord(data[offset + 1])) shl 8)

proc rotl16(value: uint16, count: int): uint16 =
  let shift = count and 15
  if shift == 0: value
  else: (value shl shift) or (value shr (16 - shift))

if paramCount() != 1:
  quit("usage: sealed-viewer PROGRAM", 2)

let program = readFile(paramStr(1))
if program.len mod 6 != 0:
  quit("invalid program length", 3)

var registers: array[4, uint16]
var memory: array[256, uint8]
var zero = false
var pc = 0
var steps = 0
while pc >= 0 and pc < program.len div 6 and steps < 4096:
  let offset = pc * 6
  let opcode = u16(program, offset)
  let dst = ord(program[offset + 2])
  let src = ord(program[offset + 3])
  let immediate = u16(program, offset + 4)
  if dst > 3 or src > 3:
    quit("invalid register", 4)
  inc steps
  case opcode
  of 0x01'u16:
    registers[dst] = immediate
    zero = registers[dst] == 0
    inc pc
  of 0x02'u16:
    registers[dst] = uint16(memory[(int(registers[src]) + int(immediate)) and 0xff])
    zero = registers[dst] == 0
    inc pc
  of 0x03'u16:
    registers[dst] = registers[dst] xor registers[src] xor immediate
    zero = registers[dst] == 0
    inc pc
  of 0x04'u16:
    registers[dst] = registers[dst] + registers[src] + immediate
    zero = registers[dst] == 0
    inc pc
  of 0x05'u16:
    registers[dst] = rotl16(registers[src], int(immediate))
    zero = registers[dst] == 0
    inc pc
  of 0x06'u16:
    memory[(int(registers[dst]) + int(immediate)) and 0xff] = uint8(registers[src] and 0xff)
    inc pc
  of 0x07'u16:
    if not zero: pc += int(cast[int16](immediate))
    else: inc pc
  of 0xff'u16:
    break
  else:
    quit("invalid opcode", 5)

if steps >= 4096:
  quit("instruction limit", 6)

echo $(%*{"registers": [registers[0], registers[1], registers[2], registers[3]],
            "memory_40_80": memory[0x40 .. 0x7f], "steps": steps})
