from selfdrive.dragon import dragon_conf
import subprocess
import os
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))

letters = { "a":[ "###", "# #", "###", "# #", "# #"], "b":[ "###", "# #", "###", "# #", "###"], "c":[ "###", "#", "#", "#", "###"], "d":[ "##", "# #", "# #", "# #", "##"], "e":[ "###", "#", "###", "#", "###"], "f":[ "###", "#", "###", "#", "#"], "g":[ "###", "# #", "###", "  #", "###"], "h":[ "# #", "# #", "###", "# #", "# #"], "i":[ "###", " #", " #", " #", "###"], "j":[ "###", " #", " #", " #", "##"], "k":[ "# #", "##", "#", "##", "# #"], "l":[ "#", "#", "#", "#", "###"], "m":[ "# #", "###", "###", "# #", "# #"], "n":[ "###", "# #", "# #", "# #", "# #"], "o":[ "###", "# #", "# #", "# #", "###"], "p":[ "###", "# #", "###", "#", "#"], "q":[ "###", "# #", "###", "  #", "  #"], "r":[ "###", "# #", "##", "# #", "# #"], "s":[ "###", "#", "###", "  #", "###"], "t":[ "###", " #", " #", " #", " #"], "u":[ "# #", "# #", "# #", "# #", "###"], "v":[ "# #", "# #", "# #", "# #", " #"], "w":[ "# #", "# #", "# #", "###", "###"], "x":[ "# #", " #", " #", " #", "# #"], "y":[ "# #", "# #", "###", "  #", "###"], "z":[ "###", "  #", " #", "#", "###"], " ":[ " "], "1":[ " #", "##", " #", " #", "###"], "2":[ "###", "  #", "###", "#", "###"], "3":[ "###", "  #", "###", "  #", "###"], "4":[ "#", "#", "# #", "###", "  #"], "5":[ "###", "#", "###", "  #", "###"], "6":[ "###", "#", "###", "# #", "###"], "7":[ "###", "  # ", " #", " #", "#"], "8":[ "###", "# #", "###", "# #", "###"], "9":[ "###", "# #", "###", "  #", "###"], "0":[ "###", "# #", "# #", "# #", "###"], "!":[ " # ", " # ", " # ", "   ", " # "], "?":[ "###", "  #", " ##", "   ", " # "], ".":[ "   ", "   ", "   ", "   ", " # "], "]":[ "   ", "   ", "   ", "  #", " # "], "/":[ "  #", "  #", " # ", "# ", "# "], ":":[ "   ", " # ", "   ", " # ", "   "], "@":[ "###", "# #", "## ", "#  ", "###"], "'":[ " # ", " # ", "   ", "   ", "   "], "#":[ " # ", "###", " # ", "###", " # "], "-":[ "  ", "  ","###","   ","   "] }
# letters stolen from here: http://www.stuffaboutcode.com/2013/08/raspberry-pi-minecraft-twitter.html

def print_letters(text):
    bigletters = []
    for i in text:
        bigletters.append(letters.get(i.lower(),letters[' ']))
    output = ['']*5
    for i in range(5):
        for j in bigletters:
            temp = ' '
            try:
                temp = j[i]
            except:
                pass
            temp += ' '*(5-len(temp))
            temp = temp.replace(' ',' ')
            temp = temp.replace('#','@')
            output[i] += temp
    return '\n'.join(output)
import sys, termios, tty, os, time

def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

button_delay = 0.2

dragon = dragon_conf()
dragon.conf['tuneGernby'] = "1"
dragon.write_config(dragon.conf)
param = ["iLG", "oLG", "timeConstant", "actuatorEffect"]

j = 0
while True:
  print ("")
  print (print_letters(param[j][0:9]))
  print ("")
  print (print_letters(dragon.conf[param[j]]))
  print ("")
  print ("1,3,5,7,r to incr 0.1,0.05,0.01,0.001,0.00001")
  print ("a,d,g,j,v to decr 0.1,0.05,0.01,0.001,0.00001")
  print ("0 / L to make the value 0 / 1")
  print ("press SPACE / m for next /prev parameter")
  print ("press z to quit")

  char  = getch()
  write_json = False
  if (char == "v"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) - 0.00001),5))
    write_json = True

  if (char == "r"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) + 0.00001),5))
    write_json = True
    
  if (char == "7"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) + 0.001),5))
    write_json = True

  if (char == "5"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) + 0.01),5))
    write_json = True

  elif (char == "3"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) + 0.05),5))
    write_json = True

  elif (char == "1"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) + 0.1),5))
    write_json = True

  elif (char == "j"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) - 0.001),5))
    write_json = True

  elif (char == "g"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) - 0.01),5))
    write_json = True

  elif (char == "d"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) - 0.05),5))
    write_json = True

  elif (char == "a"):
    dragon.conf[param[j]] = str(round((float(dragon.conf[param[j]]) - 0.1),5))
    write_json = True

  elif (char == "0"):
    dragon.conf[param[j]] = "0"
    write_json = True

  elif (char == "l"):
    dragon.conf[param[j]] = "1"
    write_json = True

  elif (char == " "):
    if j < len(param) - 1:
      j = j + 1
    else:
      j = 0

  elif (char == "m"):
    if j > 0:
      j = j - 1
    else:
      j = len(param) - 1

  elif (char == "z"):
    process.kill()
    break

  if float(dragon.conf['tuneGernby']) != 1 and float(dragon.conf['tuneGernby']) != 0:
    dragon.conf['tuneGernby'] = "1"

  if float(dragon.conf['iLG']) < 0 and float(dragon.conf['iLG']) != -1:
    dragon.conf['iLG'] = "0"

  if float(dragon.conf['iLG']) > 8:
    dragon.conf['iLG'] = "8"

  if float(dragon.conf['oLG']) < 0 and float(dragon.conf['oLG']) != -1:
    dragon.conf['oLG'] = "0"

  if float(dragon.conf['oLG']) > 10:
    dragon.conf['oLG'] = "10"
    
  if dragon.conf['timeConstant'] < "0" and dragon.conf['timeConstant'] != -1:
    dragon.conf['timeConstant'] = "0"
    
  if float(dragon.conf['timeConstant']) > 3:
    dragon.conf['timeConstant'] = "3"
    
  if dragon.conf['actuatorEffect'] < "1" and dragon.conf['actuatorEffect'] != -1:
    dragon.conf['actuatorEffect'] = "1"
    
  if float(dragon.conf['actuatorEffect']) > 3:
    dragon.conf['actuatorEffect'] = "3"
 
  if write_json:
    dragon.write_config(dragon.conf)

  time.sleep(button_delay)

else:
  process.kill()
