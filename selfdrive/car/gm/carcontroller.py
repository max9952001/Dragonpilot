from cereal import car
from common.realtime import DT_CTRL
from common.numpy_fast import interp
from selfdrive.config import Conversions as CV
from selfdrive.car import apply_std_steer_torque_limits
from selfdrive.car.gm import gmcan
from selfdrive.car.gm.values import DBC, CanBus, AccState
from opendbc.can.packer import CANPacker

VisualAlert = car.CarControl.HUDControl.VisualAlert


class CarControllerParams():
  def __init__(self):
    self.STEER_MAX = 300
    self.STEER_STEP = 1              # how often we update the steer cmd
    self.STEER_DELTA_UP = 3          # ~0.75s time to peak torque (255/50hz/0.75s)
    self.STEER_DELTA_DOWN = 3       # ~0.3s from peak torque to zero
    self.MIN_STEER_SPEED = 3.
    self.STEER_DRIVER_ALLOWANCE = 50   # allowed driver torque before start limiting
    self.STEER_DRIVER_MULTIPLIER = 4   # weight driver torque heavily
    self.STEER_DRIVER_FACTOR = 100     # from dbc
    self.NEAR_STOP_BRAKE_PHASE = 0.5 # m/s, more aggressive braking near full stop

    # Takes case of "Service Adaptive Cruise" and "Service Front Camera"
    # dashboard messages.
    self.ADAS_KEEPALIVE_STEP = 100
    self.CAMERA_KEEPALIVE_STEP = 100

    # pedal lookups, only for Volt
    MAX_GAS = 3072              # Only a safety limit
    self.ZERO_GAS = 2048
    MAX_BRAKE = 350             # Should be around 3.5m/s^2, including regen
    self.MAX_ACC_REGEN = 1404  # ACC Regen braking is slightly less powerful than max regen paddle
    self.GAS_LOOKUP_BP = [-0.25, 0., 0.5]
    self.GAS_LOOKUP_V = [self.MAX_ACC_REGEN, self.ZERO_GAS, MAX_GAS]
    self.BRAKE_LOOKUP_BP = [-1., -0.25]
    self.BRAKE_LOOKUP_V = [MAX_BRAKE, 0]


def actuator_hystereses(final_pedal, pedal_steady):
  # hyst params... TODO: move these to VehicleParams
  pedal_hyst_gap = 0.01    # don't change pedal command for small oscillations within this value

  # for small pedal oscillations within pedal_hyst_gap, don't change the pedal command
  if final_pedal == 0.:
    pedal_steady = 0.
  elif final_pedal > pedal_steady + pedal_hyst_gap:
    pedal_steady = final_pedal - pedal_hyst_gap
  elif final_pedal < pedal_steady - pedal_hyst_gap:
    pedal_steady = final_pedal + pedal_hyst_gap
  final_pedal = pedal_steady

  return final_pedal, pedal_steady

class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.pedal_steady = 0.
    self.start_time = 0.
    self.apply_steer_last = 0
    self.steer_max = 0.
    self.lka_icon_status_last = (False, False)
    self.steer_rate_limited = False
    self.fcw_frames = 0

    self.params = CarControllerParams()

    self.packer_pt = CANPacker(DBC[CP.carFingerprint]['pt'])
    self.packer_ch = CANPacker(DBC[CP.carFingerprint]['chassis'])

  def update(self, enabled, CS, frame, actuators, \
             hud_v_cruise, hud_show_lanes, hud_show_car, hud_alert):

    P = self.params

    # Send CAN commands.
    can_sends = []

    # FCW: trigger FCWAlert for 100 frames (4 seconds)
    if hud_alert == VisualAlert.fcw:
      self.fcw_frames = 100

    ### STEER ###

    if (frame % P.STEER_STEP) == 0:
      lkas_enabled = enabled and not CS.out.steerWarning and CS.out.vEgo > P.MIN_STEER_SPEED
      if lkas_enabled:
        if CS.out.vEgo < 8.0:
          self.steer_max = 180
        elif CS.out.vEgo < 12.5:
          self.steer_max = 220
        elif CS.out.vEgo < 16.6:
          self.steer_max = 250
        elif CS.out.vEgo < 20.0:
          self.steer_max = 260
        else:
          self.steer_max = P.STEER_MAX * 0.9
        new_steer = actuators.steer * self.steer_max
        apply_steer = apply_std_steer_torque_limits(new_steer, self.apply_steer_last, CS.out.steeringTorque, P)
        self.steer_rate_limited = new_steer != apply_steer
      else:
        apply_steer = 0

      self.apply_steer_last = apply_steer
      idx = (frame // P.STEER_STEP) % 4

      can_sends.append(gmcan.create_steering_control(self.packer_pt,
        CanBus.POWERTRAIN, apply_steer, idx, lkas_enabled))

    ### GAS/BRAKE ###

    # no output if not enabled, but keep sending keepalive messages
    # treat pedals as one
    final_pedal = actuators.gas - actuators.brake

    # *** apply pedal hysteresis ***
    final_brake, self.brake_steady = actuator_hystereses(
      final_pedal, self.pedal_steady)

    if not enabled:
      # Stock ECU sends max regen when not enabled.
      apply_gas = P.MAX_ACC_REGEN
      apply_brake = 0
    else:
      apply_gas = int(round(interp(final_pedal, P.GAS_LOOKUP_BP, P.GAS_LOOKUP_V)))
      apply_brake = int(round(interp(final_pedal, P.BRAKE_LOOKUP_BP, P.BRAKE_LOOKUP_V)))

    # Gas/regen and brakes - all at 25Hz
    if (frame % 4) == 0:
      idx = (frame // 4) % 4

      #at_full_stop = enabled and CS.out.standstill
      #near_stop = enabled and (CS.out.vEgo < P.NEAR_STOP_BRAKE_PHASE)
      car_stopping = apply_gas < P.ZERO_GAS
      standstill = CS.pcm_acc_status == AccState.STANDSTILL
      at_full_stop = enabled and standstill and car_stopping
      near_stop = enabled and (CS.out.vEgo < P.NEAR_STOP_BRAKE_PHASE) and car_stopping
      can_sends.append(gmcan.create_friction_brake_command(self.packer_ch, CanBus.CHASSIS, apply_brake, idx, near_stop, at_full_stop))

      #at_full_stop = enabled and CS.out.standstill
      #can_sends.append(gmcan.create_gas_regen_command(self.packer_pt, CanBus.POWERTRAIN, apply_gas, idx, enabled, at_full_stop))

    # Send dashboard UI commands (ACC status), 25hz
    if (frame % 4) == 0:
      # Send FCW if applicable
      send_fcw = 0
      if self.fcw_frames > 0:
        send_fcw = 0x3
        self.fcw_frames -= 1
      can_sends.append(gmcan.create_acc_dashboard_command(self.packer_pt, CanBus.POWERTRAIN, enabled, hud_v_cruise * CV.MS_TO_KPH, hud_show_car, send_fcw))

    # Radar needs to know current speed and yaw rate (50hz),
    # and that ADAS is alive (10hz)
    time_and_headlights_step = 10
    tt = frame * DT_CTRL

    if frame % time_and_headlights_step == 0:
      idx = (frame // time_and_headlights_step) % 4
      can_sends.append(gmcan.create_adas_time_status(CanBus.OBSTACLE, int((tt - self.start_time) * 60), idx))
      can_sends.append(gmcan.create_adas_headlights_status(CanBus.OBSTACLE))

    speed_and_accelerometer_step = 2
    if frame % speed_and_accelerometer_step == 0:
      idx = (frame // speed_and_accelerometer_step) % 4
      can_sends.append(gmcan.create_adas_steering_status(CanBus.OBSTACLE, idx))
      can_sends.append(gmcan.create_adas_accelerometer_speed_status(CanBus.OBSTACLE, CS.out.vEgo, idx))

    if frame % P.ADAS_KEEPALIVE_STEP == 0:
      can_sends += gmcan.create_adas_keepalive(CanBus.POWERTRAIN)

    # Show green icon when LKA torque is applied, and
    # alarming orange icon when approaching torque limit.
    # If not sent again, LKA icon disappears in about 5 seconds.
    # Conveniently, sending camera message periodically also works as a keepalive.
    lka_active = CS.lkas_status == 1
    lka_critical = lka_active and abs(actuators.steer) > 0.9
    lka_icon_status = (lka_active, lka_critical)
    if frame % P.CAMERA_KEEPALIVE_STEP == 0 \
        or lka_icon_status != self.lka_icon_status_last:
      steer_alert = hud_alert == VisualAlert.steerRequired
      can_sends.append(gmcan.create_lka_icon_command(CanBus.SW_GMLAN, lka_active, lka_critical, steer_alert))
      self.lka_icon_status_last = lka_icon_status

    return can_sends
