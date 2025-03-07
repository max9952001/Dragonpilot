from cereal import car
from selfdrive.swaglog import cloudlog
from selfdrive.controls.lib.drive_helpers import create_event, EventTypes as ET
from selfdrive.car.volkswagen.values import CAR, BUTTON_STATES, NWL, TRANS, GEAR, MQB_CARS, PQ_CARS
from common.params import Params
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, gen_empty_fingerprint
from selfdrive.car.interfaces import CarInterfaceBase

class CarInterface(CarInterfaceBase):
  def __init__(self, CP, CarController, CarState):
    super().__init__(CP, CarController, CarState)

    self.displayMetricUnitsPrev = None
    self.gas_pressed_prev = False
    self.brake_pressed_prev = False
    self.cruise_enabled_prev = False
    self.low_speed_alert = False
    self.buttonStatesPrev = BUTTON_STATES.copy()

    # Set up an alias to PT/CAM parser for ACC depending on its detected network location
    self.cp_acc = self.cp if CP.networkLocation == NWL.fwdCamera else self.cp_cam

  @staticmethod
  def compute_gb(accel, speed):
    return float(accel) / 4.0

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), has_relay=False, car_fw=[]):
    ret = CarInterfaceBase.get_std_params(candidate, fingerprint, has_relay)

    # Set global default parameters
    ret.radarOffCan = True
    ret.enableCamera = True  # Stock camera detection doesn't apply to VW
    ret.steerRateCost = 1.0
    ret.steerActuatorDelay = 0.05  # Hopefully all racks are similar here
    ret.steerLimitTimer = 0.4

    # Override these per-car as necessary
    ret.lateralTuning.pid.kpBP = [0.]
    ret.lateralTuning.pid.kiBP = [0.]
    ret.lateralTuning.pid.kpV = [0.6]
    ret.lateralTuning.pid.kiV = [0.2]
    ret.lateralTuning.pid.kf = 0.00006

    # PER-PLATFORM PARAMETERS - DO NOT EDIT HERE TO TUNE INDIVIDUAL VEHICLES

    if candidate in MQB_CARS:
      # Configurations shared between all MQB vehicles
      ret.carName = "volkswagen"
      ret.safetyModel = car.CarParams.SafetyModel.volkswagen

      # Determine installed network location and trans type from fingerprint
      ret.networkLocation = NWL.fwdCamera if 0x122 in fingerprint[0] else NWL.gateway
      if 0xAD in fingerprint[0]:  # Getriebe_11
        ret.transmissionType = TRANS.automatic
      elif 0x187 in fingerprint[0]:  # EV_Gearshift
        ret.transmissionType = TRANS.direct
      else:  # No trans at all
        ret.transmissionType = TRANS.manual

    elif candidate in PQ_CARS:
      # Configurations shared between all PQ35/PQ46/NMS vehicles
      ret.carName = "volkswagen"
      ret.safetyModel = car.CarParams.SafetyModel.volkswagenPq

      # Determine installed network location and trans type from fingerprint
      ret.networkLocation = NWL.fwdCamera if 0x368 in fingerprint[0] else NWL.gateway
      if 0x440 in fingerprint[0]:  # Getriebe_1
        ret.transmissionType = TRANS.automatic
      else:  # No trans at all
        ret.transmissionType = TRANS.manual

    cloudlog.warning("Detected network location: %s", ret.networkLocation)
    cloudlog.warning("Detected transmission type: %s", ret.transmissionType)

    # PER-VEHICLE PARAMETERS - EDIT HERE TO TUNE INDIVIDUAL VEHICLES

    if candidate == CAR.GENERICMQB:
      # FIXME: Defaulting to VW Golf Mk7 as a baseline.
      ret.mass = 1500 + STD_CARGO_KG  # Average, varies on trim/package
      ret.wheelbase = 2.64
      ret.centerToFront = ret.wheelbase * 0.45  # Estimated
      ret.steerRatio = 15.6
      tire_stiffness_factor = 1.0

    elif candidate == CAR.GENERICPQ:
      ret.mass = 1375 + STD_CARGO_KG  # Average, varies on trim/package
      ret.wheelbase = 2.58
      ret.centerToFront = ret.wheelbase * 0.45  # Estimated
      ret.steerRatio = 15.6
      tire_stiffness_factor = 1.0

    # TODO: get actual value, for now starting with reasonable value for
    # civic and scaling by mass and wheelbase
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)

    return ret

  # returns a car.CarState
  def update(self, c, can_strings):
    canMonoTimes = []
    buttonEvents = []
    params = Params()

    # Process the most recent CAN message traffic, and check for validity
    # The camera CAN has no signals we use at this time, but we process it
    # anyway so we can test connectivity with can_valid
    self.cp.update_strings(can_strings)
    self.cp_cam.update_strings(can_strings)

    ret = self.CS.update(self.cp, self.cp_cam, self.cp_acc, self.CP.transmissionType)
    ret.canValid = self.cp.can_valid  # FIXME: Restore cp_cam valid check after proper LKAS camera detect
    ret.steeringRateLimited = self.CC.steer_rate_limited if self.CC is not None else False

    # Update the EON metric configuration to match the car at first startup,
    # or if there's been a change.
    if self.CS.displayMetricUnits != self.displayMetricUnitsPrev:
      params.put("IsMetric", "1" if self.CS.displayMetricUnits else "0")

    # Check for and process state-change events (button press or release) from
    # the turn stalk switch or ACC steering wheel/control stalk buttons.
    for button in self.CS.buttonStates:
      if self.CS.buttonStates[button] != self.buttonStatesPrev[button]:
        be = car.CarState.ButtonEvent.new_message()
        be.type = button
        be.pressed = self.CS.buttonStates[button]
        buttonEvents.append(be)

    events = self.create_common_events(ret, extra_gears=[GEAR.eco, GEAR.sport])

    # Vehicle health and operation safety checks
    if self.CS.parkingBrakeSet:
      events.append(create_event('parkBrake', [ET.NO_ENTRY, ET.USER_DISABLE]))
    if self.CS.steeringFault:
      events.append(create_event('steerTempUnavailable', [ET.NO_ENTRY, ET.WARNING]))

    # Engagement and longitudinal control using stock ACC. Make sure OP is
    # disengaged if stock ACC is disengaged.
    if not ret.cruiseState.enabled:
      events.append(create_event('pcmDisable', [ET.USER_DISABLE]))
    # Attempt OP engagement only on rising edge of stock ACC engagement.
    elif not self.cruise_enabled_prev:
      events.append(create_event('pcmEnable', [ET.ENABLE]))

    ret.events = events
    ret.buttonEvents = buttonEvents
    ret.canMonoTimes = canMonoTimes

    # update previous car states
    self.gas_pressed_prev = ret.gasPressed
    self.brake_pressed_prev = ret.brakePressed
    self.cruise_enabled_prev = ret.cruiseState.enabled
    self.displayMetricUnitsPrev = self.CS.displayMetricUnits
    self.buttonStatesPrev = self.CS.buttonStates.copy()

    self.CS.out = ret.as_reader()
    return self.CS.out

  def apply(self, c):
    can_sends = self.CC.update(c.enabled, self.CS, self.frame, c.actuators,
                   c.hudControl.visualAlert,
                   c.hudControl.audibleAlert,
                   c.hudControl.leftLaneVisible,
                   c.hudControl.rightLaneVisible)
    self.frame += 1
    return can_sends
