import json
import os

class dragon_conf():
  def __init__(self, CP=None):
    self.conf = self.read_config()
    if CP is not None:
      self.init_config(CP)

    # only fetch innerLoopGain, outerLoopGain, timeConstant and actuatorEffectiveness from interface.py if it's a INDI controlled car
    if CP.lateralTuning.which() == 'indi':
      if self.conf['iLG'] == "-1":
        self.conf['iLG'] = str(round(CP.lateralTuning.indi.innerLoopGain,1))
        write_conf = True
      if self.conf['oLG'] == "-1":
        self.conf['oLG'] = str(round(CP.lateralTuning.indi.outerLoopGain,1))
        write_conf = True
      if self.conf['timeConstant'] == "-1":
        self.conf['timeConstant'] = str(round(CP.lateralTuning.indi.timeConstant,2))
        write_conf = True
      if self.conf['actuatorEffect'] == "-1":
        self.conf['actuatorEffect'] = str(round(CP.lateralTuning.indi.actuatorEffectiveness,2))
        write_conf = True

    if write_conf:
      self.write_config(self.config)

  def read_config(self):
    self.element_updated = False

    if os.path.isfile('/data/dragon.json'):
      with open('/data/dragon.json', 'r') as f:
        self.config = json.load(f)

      if self.element_updated:
        print("updated")
        self.write_config(self.config)

    else:
      self.config = {"iLG":"-1", "oLG":"-1", "timeConstant":"-1", "actuatorEffect":"-1"}

      self.write_config(self.config)
    return self.config

  def write_config(self, config):
    try:
      with open('/data/dragon.json', 'w') as f:
        json.dump(self.config, f, indent=2, sort_keys=True)
        os.chmod("/data/dragon.json", 0o764)
    except IOError:
      os.mkdir('/data')
      with open('/data/dragon.json', 'w') as f:
        json.dump(self.config, f, indent=2, sort_keys=True)
        os.chmod("/data/dragon.json", 0o764)
