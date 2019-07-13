#!/user/bin/env python2.7
import RPi.GPIO as GPIO
import phant
import time as time_
import sqlite3 as sqlite
import threading, datetime

GPIO.setmode(GPIO.BCM)

time_zone = -5
distance = 0
distance_per_rev = 0.00056613129
distance_per_sense = distance_per_rev / 2.0
last_time = 0
avg_speed = 0
max_speed = 0
speed = 0
count = 0
sum_speed = 0
total_time = 0
t = None
r = None
p = None

#GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
#GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)

lock = threading.Lock()

def millis():
    return int(round(time_.time() * 1000))

def sensor(channel):
	global distance
	global speed
	global avg_speed
	global count
	global last_time
	global sum_speed
	global total_time
	now = millis()
	if (now - last_time) > 10000:
		lock.acquire()
		count = 0
		avg_speed = 0
		sum_speed = 0
		lock.release()
	if (now - last_time) < 5000:
		total_time += (now - last_time)
	speed = distance_per_sense / (now - last_time)
	speed = speed * 3600000
#	if speed < 8:
	lock.acquire()
	sum_speed = sum_speed + speed
	count = count + 1
	avg_speed = (sum_speed) / (count)
#	print "SS: %f, C: %d" % (sum_speed, count)
	lock.release()
	distance += distance_per_sense
	last_time = millis()

p = phant.Phant('REPLACEME', 'distance', 'speed', 'time', private_key='REPLACEME')

next_call = time_.time()

def phantupdate():
	global next_call
	global distance
	global max_speed
	global avg_speed
	global sum_speed
	global count
	global total_time
	global t
	global p
	now = millis()
	if (last_time > 0) and (now - last_time) < 10000 and count > 1:
		lock.acquire()
		dist = distance
		aspeed = avg_speed
		avg_speed = 0
		count = 0
		sum_speed = 0
		lock.release()
		p.log(dist,aspeed,now)
		if(aspeed > max_speed):
			max_speed = aspeed
	next_call = next_call + 10
	t = threading.Timer( next_call - time_.time(), phantupdate )
	t.start()

next_reset = time_.time() #get time
next_reset += (time_zone * 3600) #convert to local time
next_reset //= 86400 #get the current days
next_reset *= 86400 #set back to seconds
next_reset += 75600 #add for 9pm
next_reset -= (time_zone * 3600) #set back to UTC

def scriptreset():
	global r
	global next_reset
	global distance
	global max_speed
	global count
	global speed
	global sum_speed
	global total_time
	global last_time
	#write data into the daily db
	if(last_time > 0):
		#convert total time to millis
		now = time_.time()
		hours, milliseconds = divmod(total_time, 3600000)
                minutes, milliseconds = divmod(total_time, 60000)
                minutes %= 60
                seconds = float(milliseconds) / 1000
		time = "%i:%02i:%06.3f" % (hours, minutes, seconds)
		db = sqlite.connect("pig.db")
		cur = db.cursor()
		cur.execute("""INSERT INTO wheel (date, time, dist, MSpeed) VALUES(?,?,?,?);""", (now,time, distance, max_speed))
		db.commit()
		db.close()
		print "Script Reset\n"
	#reset the variables
	distance = 0
	max_speed = 0
	count = 0
	speed = 0
	sum_speed = 0
	total_time = 0
	last_time = 0
	next_reset = next_reset + 86400
        r = threading.Timer( next_reset - time_.time(), scriptreset )
        r.start()

#GPIO.add_event_detect(24, GPIO.RISING, callback=sensor,bouncetime=25)
GPIO.add_event_detect(24, GPIO.FALLING, callback=sensor,bouncetime=25)

try:
	scriptreset()
	phantupdate()
	print "Script init started\n"
	while True:
		#time_.sleep(600)
		raw_input("Press Enter for Status")
		print "Distance: %f - Max Speed: %0.2f" % (distance, max_speed)
		hours, milliseconds = divmod(total_time, 3600000)
		minutes, milliseconds = divmod(total_time, 60000)
		minutes %= 60
		seconds = float(milliseconds) / 1000
		s = "%i:%02i:%06.3f" % (hours, minutes, seconds)
		print "Run Time: %s" % s
except KeyboardInterrupt:
	GPIO.cleanup()
	t.cancel()
	r.cancel()
GPIO.cleanup()
t.cancel()
r.cancel()
