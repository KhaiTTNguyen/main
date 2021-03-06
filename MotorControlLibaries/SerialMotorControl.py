#!/usr/bin/env python

#Sam Wilson, 4/7/2017

from SabertoothPacketizedSerialInterface import *
from math import ceil

#This is the serial interface for controlling a bank of Sabertooth 2x25 Motor Controllers.
spsi = SPSI('/dev/ttyS0')

#List of addresses currently in use and therefore not available for assignment
usedAddresses = []

#Remaps values from [-1.0, 1.0] to [0, 127]
def speed2byte(speed, forceIntoRange = True):
    if forceIntoRange:
        if speed < -1.0:
            speed = -1.0
        elif speed > 1.0:
            speed = 1.0
    return int(ceil(abs(speed) * 127))

#Checks if the address is valid. Throws errors for addresses already in use or out of range
def validateAddress(address):
    if address < 128 or address > 135:
        raise ValueError("Controller address {} is not in the range [128, 135]".format(address))
    elif address in usedAddresses:
        raise Exception("Address {} is already in use".format(address))
    else:
        return

#For standard reversible DC Motors
class DCMotor:

    def __init__(address, motorNumber):

        #Confirms the supplied address is acceptable. Does not handle errors locally
        validateAddress(address)

        #Saves the address and locks its use from other objects
        self.address = address
        usedAddresses.append(address)

        #Assigns the correct serial commands based on what number the motor is
        if motorNumber == 1:
            self.forwardCommand = motorCommand['M1:Forward']
            self.backwardCommand = motorCommand['M1:Backward']
        elif motorNumber == 2:
            self.forwardCommand = motorCommand['M2:Forward']
            self.backwardCommand = motorCommand['M2:Backward']
        else:
            raise ValueError("Sabertooth motor numbers must be 1 or 2, not {}".format(motorNumber))

        #A software solution to inverting a motor's controls
        if invertCommands:
            self.forwardCommand, self.backwardCommand = self.backwardCommand, self.forwardCommand

        #Starts the motor at a stopped position, for safety and convenience
        self.setSpeed(0.0)

    #Stops the motor and frees up its address
    def __del__():

        self.setSpeed(0.0)
        usedAddresses.remove(self.address)

    #Takes in a value in the range [-1.0, 1.0]
    def setSpeed(speed):

        #Sets the backwards flag
        if speed < 0.0:
            backwards = True
        else:
            backwards = False

        #Converts raw speed into the appropriate serial byte
        data = speed2byte(speed)

        #Sends the serial packet for the command
        if backwards:
            spsi.sendPacket(self.address, self.backwardCommand, data)
        else:
            spsi.sendPacket(self.address, self.forwardCommand, data)

    #Sets the speed to 0
    def stop():
        self.setSpeed(0.0)

#For DC motor powered Liner Actuators
class LinearActuator:

    def __init__(address, motorNumber, invertCommands = False):

        #Confirms the supplied address is acceptable. Does not handle errors locally
        validateAddress(address)

        #Saves the address and locks its use from other objects
        self.address = address
        usedAddresses.append(address)

        #Assigns the correct serial commands based on what number the motor is
        if motorNumber == 1:
            self.forwardCommand = motorCommand['M1:Forward']
            self.backwardCommand = motorCommand['M1:Backward']
        elif motorNumber == 2:
            self.forwardCommand = motorCommand['M2:Forward']
            self.backwardCommand = motorCommand['M2:Backward']
        else:
            raise ValueError("Sabertooth motor numbers must be 1 or 2, not {}".format(motorNumber))

        #A software solution to inverting a motor's controls
        if invertCommands:
            self.forwardCommand, self.backwardCommand = self.backwardCommand, self.forwardCommand

        #Starts the motor at a stopped position, for safety and convenience
        self._setSpeed(0.0)

    #Stops the motor and frees up its address
    def __del__():

        self._setSpeed(0.0)
        usedAddresses.remove(self.address)

    #Takes in a value in the range [-1.0, 1.0]
    #Lightly hidden for liner actuators in favor of extend and retract
    def _setSpeed(speed):

        #Sets the backwards flag
        if speed < 0.0:
            backwards = True
        else:
            backwards = False

        #Converts raw speed into the appropriate serial byte
        data = speed2byte(speed)

        #Sends the serial packet for the command
        if backwards:
            spsi.sendPacket(self.address, self.backwardCommand, data)
        else:
            spsi.sendPacket(self.address, self.forwardCommand, data)

    #Sets the speed to 0
    def stop():
        self.setSpeed(0.0)

    #Takes a speed input from (0.0, 1.0], to adjust rate of extension
    def extend(speed = 1.0):

        #Values outside of the acceptable range will be mapped to full speed
        if speed < 0.0:
            speed = 1.0

        #Converts raw speed into the appropriate serial byte
        data = speed2byte(speed)

        #Sends the serial packet for the command
        spsi.sendPacket(self.address, self.forwardCommand, data)

    #Takes a speed input from (0.0, 1.0], to adjust rate of retraction
    def retract(speed = 1.0):

        #Values outside of the acceptable range will be mapped to full speed
        if speed < 0.0:
            speed = 1.0

        #Converts raw speed into the appropriate serial byte
        data = speed2byte(speed)

        #Sends the serial packet for the command
        spsi.sendPacket(self.address, self.backwardCommand, data)

#A class that utilizes the Sabretooth controller's built-in tank-style drive functionality
class Drivetrain:

    def __init__(address, invertY = False, invertX = False, swapDriveCommands = False, swapTurnCommands = False):

        #Confirms the supplied address is acceptable. Does not handle errors locally
        validateAddress(address)

        #Saves the address and locks its use from other objects
        self.address = address
        usedAddresses.append(address)

        #Stores the axis inversion flags
        self.invertY = invertY
        self.invertX = invertX

        #Added to allow a quick solution for fixing motors that aren't operating correctly
        if not swapDriveCommands:
            self.forwardCommand = motorCommand['MM:Forward']
            self.backwardCommand = motorCommand['MM:Backward']
        else:
            self.forwardCommand = motorCommand['MM:Backward']
            self.backwardCommand = motorCommand['MM:Forward']

        #Added to allow a quick solution for fixing motors that aren't operating correctly
        if not swapTurnCommands:
            self.rightCommand = motorCommand['MM:TurnRight']
            self.leftCommand = motorCommand['MM:TurnLeft']
        else:
            self.rightCommand = motorCommand['MM:TurnLeft']
            self.leftCommand = motorCommand['MM:TurnRight']

        #Starts the motors safely. Also, mixed mode will not function until both a drive and turn packet have been sent once
        self._setSpeed(0.0)
        self._setTurn(0.0)

    #Stops the motors when this object is deleted
    def __del__():

        self._setSpeed(0.0)
        self._setTurn(0.0)
        usedAddresses.remove(self.address)

    #Takes in a value in the range [-1.0, 1.0] to set the speed of the drivetrain
    #Lightly hidden in favor of drive(x, y)
    def _setSpeed(speed):

        #Sets the backwards flag
        if speed < 0.0:
            backwards = True
        else:
            backwards = False

        #Converts raw speed into the appropriate serial byte
        data = speed2byte(speed)

        #Sends the serial packet for the command
        if backwards:
            spsi.sendPacket(self.address, self.backwardCommand, data)
        else:
            spsi.sendPacket(self.address, self.forwardCommand, data)

    #Takes in a value in the range [-1.0, 1.0] to set the turn of the drivetrain
    #Lightly hidden in favor of drive(x, y)
    def _setTurn(magnitude):

        #Sets the left/right flag
        if magnitude < 0.0:
            left = True
        else:
            left = False

        #Converts magnitude into the appropriate serial byte
        data = speed2byte(magnitude)

        #Sends the serial packet for the command
        if left:
            spsi.sendPacket(self.address, self.leftCommand, data)
        else:
            spsi.sendPacket(self.address, self.rightCommand, data)

    def drive(x, y):

        #Inverts inputs if necessary
        x = -x if self.invertX else x
        y = -y if self.invertY else y

        #Sends the speed and turn commands
        self._setSpeed(y)
        self._setTurn(x)
