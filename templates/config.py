'''The template of the config file
This is a template file of preparing parameters for madx and sixtracking jobs.
'''
import os
import ast
import logging

from pysixdesk.lib import submission
from pysixdesk import Study
from math import sqrt, pi, sin, cos
from pysixdesk.lib.machineparams import MachineConfig

# logger configuration
logger = logging.getLogger('pysixdesk')
logger.setLevel(logging.INFO)

# To add logging to file, do:
# -----------------------------------------------------------------------------
study_path = os.path.dirname(__file__)
log_path = os.path.join(study_path, 'pysixdesk.log')
filehandler = logging.FileHandler(log_path)
fmt = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s',
                        datefmt='%b/%d %H:%M:%S')
filehandler.setFormatter(fmt)
filehandler.setLevel(logging.DEBUG)
logger.addHandler(filehandler)
# -----------------------------------------------------------------------------


class MyStudy(Study):

    def __init__(self, name='study', location=os.getcwd()):
        super(MyStudy, self).__init__(name, location)
        '''initialize a study'''
        self.cluster_class = submission.HTCondor
        self.paths['boinc_spool'] = '/afs/cern.ch/work/b/boinc/boinctest'
        self.boinc_vars['appName'] = 'sixtracktest'

        # Database type
        self.db_info['db_type'] = 'sql'
        # self.db_info['db_type'] = 'mysql'

        # Get the default values for specified machine with specified runtype
        machine_params = MachineConfig('LHC').parameters('inj')
        # machine_params = MachineConfig('LHC').parameters('col')
        self.oneturn = True  # Switch for oneturn sixtrack job
        # self.collimation = True

        # All parameters are case-sensitive
        # the name of mask file
        self.madx_input["mask_file"] = 'hl10.mask'
        self.madx_params["SEEDRAN"] = [1, 2]  # all seeds in the study
        # all chromaticity in the study
        self.madx_params["QP"] = list(range(1, 1 + 1))
        # all octupole currents in the study
        self.madx_params["IOCT"] = list(range(100, 200 + 1, 100))
        self.oneturn_sixtrack_input['fort_file'] = 'fort.3'
        self.oneturn_sixtrack_params.update(machine_params)
        self.sixtrack_params = dict(self.oneturn_sixtrack_params)
        self.sixtrack_params['turnss'] = int(1e2)  # number of turns to track (must be int)
        amp = [8, 10, 12]  # The amplitude
        self.sixtrack_params['amp'] = list(zip(amp, amp[1:]))  # Take pairs
        self.sixtrack_params['kang'] = list(range(1, 1 + 1))  # The angle
        self.sixtrack_input['fort_file'] = 'fort.3'
        self.preprocess_output = dict(self.madx_output)
        self.sixtrack_input['input'] = dict(self.preprocess_output)
        # For CR
        self.checkpoint_restart = False
        self.first_turn = 1
        self.last_turn = 100

        # The parameters for collimation job
        # self.madx_output = {
        #     'fc.2': 'fort.2',
        #     'fc.3': 'fort.3.mad',
        #     'fc.3.aux': 'fort.3.aux',
        #     'fc.8': 'fort.8'}
        # self.collimation_input = {'aperture':'allapert.b1',
        #         'survey':'SurveyWithCrossing_XP_lowb.dat'}
        # self.oneturn_sixtrack_input['input'] = dict(self.madx_output)
        # self.preprocess_output = dict(self.madx_output)
        # self.sixtrack_input['temp'] = 'fort.3'
        # self.sixtrack_input['input'] = self.preprocess_output
        # self.sixtrack_input['additional_input'] = ['CollDB.data']
        # self.sixtrack_output = ['aperture_losses.dat', 'coll_summary.dat',
        #         'Coll_Scatter.dat']
        # self.sixtrack_params = dict(self.oneturn_sixtrack_params)
        # self.sixtrack_params['COLL'] = '/'
        # self.sixtrack_params['turnss'] = 200
        # self.sixtrack_params['nss'] = 5000
        # self.sixtrack_params['ax0s'] = 0
        # self.sixtrack_params['ax1s'] = 17
        # self.sixtrack_params['e0'] = 6500000
        # self.sixtrack_params['POST'] = '/'
        # self.sixtrack_params['POS1'] = '/'
        # self.sixtrack_params['dp2'] = 0.00
        # self.sixtrack_params['ition'] = 1
        # self.sixtrack_params['ibtype'] = 1
        # self.sixtrack_params['length'] = 26658.864
        # # eigen-emittances to be chosen to determine the coupling angle
        # self.sixtrack_params['EI'] = 3.5
        # # logical switch to calculate 4D(ilin=1) or DA approach 6D (ilin=2)
        # self.sixtrack_params['ilin'] = 1

        self.env['emit'] = 3.75
        self.env['gamma'] = 7460.5
        self.env['kmax'] = 5

        # Update the user-define parameters and objects
        self.customize()  # This call is mandatory

    def pre_calc(self, paramdict, pre_id):
        '''Further calculations for the specified parameters'''
        # The angle should be calculated before amplitude
        keys = list(paramdict.keys())
        status = []
        status.append(self.formulas('kang', 'angle', paramdict, pre_id))
        status.append(self.formulas('amp', ['ax0s', 'ax1s'], paramdict, pre_id))
        param_keys = list(paramdict.keys())
        [paramdict.pop(key) for key in param_keys if key not in keys]
        return all(status)

    def formulas(self, source, dest, paramdict, pre_id):
        '''The formulas for the further calculations,
        this function should be customized by the user!
        @source The source parameter name
        @dest  The destination parameter name
        @paramdict The parameter dictionary, the source parameter in the dict
        will be replaced by destination parameter after calculation
        @pre_id The identified preprocess job id
        @return The status'''
        if source not in paramdict.keys():
            self._logger.info("Invalid parameter name %s!" % source)
            return 0
        value = paramdict[source]
        try:
            if isinstance(value, str):
                value = ast.literal_eval(value)
        except ValueError:
            self._logger.error("Invalid source value for job %s!" % pre_id)
            return 0
        except:
            self._logger.error("Unexpected error!", exc_info=True)
            return 0
        if source == 'amp':
            if 'angle' not in paramdict.keys():
                self._logger.error("The angle should be calculated before amplitude!")
                return 0
            try:
                values = self.getval(pre_id, ['betax'])
                beta_x = values[0]
                kang = paramdict['angle']
                kang = float(kang)
                tt = abs(sin(pi / 2 * kang) / cos(pi / 2 * kang))
                ratio = 0.0 if tt < 1.0E-15 else tt**2
                emit = self.env['emit']
                gamma = self.env['gamma']
                factor = sqrt(emit / gamma)
                ax0t = factor * (sqrt(beta_x) + sqrt(beta_x * ratio) * cos(pi / 2 * kang))
                value0 = ax0t * value[0]
                value1 = ax0t * value[1]
                paramdict[dest[0]] = str(value0)
                paramdict[dest[1]] = str(value1)
                return 1
            except:
                self._logger.error("Unexpected error!", exc_info=True)
                return 0
        elif source == 'kang':
            try:
                kmax = self.env['kmax']
                value1 = value / (kmax + 1)
                paramdict[dest] = str(value1)
                return 1
            except Exception:
                self._logger.error("Unexpected error!", exc_info=True)
                return 0
        else:
            self._logger.error("There isn't a formula for parameter %s!" % dest)
            return 0
