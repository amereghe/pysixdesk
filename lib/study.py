import os
import sys
import shutil
import inspect
import itertools
import configparser
import importlib
import utils
import mad6t_oneturn

from importlib.machinery import SourceFileLoader

class Study(object):

    def __init__(self, name='example_study', loc=os.getcwd(), parent_ws = None):
        '''Constructor'''
        self.name = name
        self.location = loc
        self.parent_ws = parent_ws
        self.config = configparser.ConfigParser()
        self.config.optionxform = str #preserve case
        self.mad6t_joblist = []
        #All the requested parameters for a study
        self.paths = {}
        self.madx_params = {}
        self.madx_input = {}
        self.madx_output = {}
        self.oneturn_sixtrack_params = {}
        self.oneturn_sixtrack_input = {}
        self.oneturn_sixtrack_output = {}
        self.sixtrack_params = {}
        self.sixtrack_input = {}
        self.sixtrack_output = []
        self.tables = {}
        #initialize default values
        Study._defaults(self)

    def _defaults(self):
        '''initialize a study with some default settings'''
        self.paths["madx_exe"] = "/afs/cern.ch/user/m/mad/bin/madx"
        self.paths["sixtrack_exe"] = "/afs/cern.ch/project/sixtrack/build/sixtrack"
        self.paths["location"] = self.location
        self.paths["madx_in"] = os.path.join(self.location, "mad6t_input")
        self.paths["madx_out"] = os.path.join(self.location, "mad6t_output")
        self.paths["sixtrack_in"] = os.path.join(self.location, "sixtrack_input")
        self.paths["sixtrack_out"] = os.path.join(self.location, "sixtrack_output")
        if self.parent_ws is None:
            self.paths["templates"] = os.path.join(StudyFactory.app_path(), 'templates')
        else:
            self.paths["templates"] = os.path.join(self.parent_ws, 'templates')

        self.madx_output = {
                'fc.2': 'fort.2',
                'fc.3': 'fort.3.mad',
                'fc.3.aux': 'fort.3.aux',
                'fc.8': 'fort.8',
                'fc.16': 'fort.16',
                'fc.34': 'fort.34'}
        self.oneturn_sixtrack_params = {
                "turnss": 1,
                "nss": 1,
                "ax0s": 0.1,
                "ax1s": 0.1,
                "imc": 1,
                "iclo6": 2,
                "writebins": 1,
                "ratios": 1,
                "Runnam": 'FirstTurn',
                "idfor": 0,
                "ibtype": 0,
                "ition": 0,
                "CHRO": '/',
                "TUNE": '/',
                "POST": 'POST',
                "POS1": '',
                "ndafi": 1,
                "tunex": 62.28,
                "tuney": 60.31,
                "inttunex": 62.28,
                "inttuney": 60.31,
                "DIFF": '/DIFF',
                "DIF1": '/',
                "pmass": 938.272013,
                "emit_beam": 3.75,
                "e0": 7000,
                "bunch_charge": 1.15E11,
                "CHROM": 0,
                "chrom_eps": 0.000001,
                "dp1": 0.000001,
                "dp2": 0.000001,
                "chromx": 2,
                "chromy": 2,
                "TUNEVAL": '/',
                "CHROVAL": '/'}
        self.oneturn_sixtrack_input['input'] = self.madx_output
        self.oneturn_sixtrack_output = ['fort.10']
        self.sixtrack_output = ['fort.10']

        self.tables = {
                "mad6t_run": ['seed', 'mad_in', 'mad_out', 'fort.2', 'fort.3',\
                        'fort.8', 'fort.16', 'job_stdout', 'job_stderr',\
                        'job_stdlog', 'mad_out_mtime'],
                "six_input": list(self.sixtrack_params.keys()) + ['id_mad6t_run'],
                "six_beta": ['seed', 'tunex', 'tuney', 'beta11', 'beta12',\
                        'beta22', 'beta21', 'qx', 'qy', 'id_mad6t_run'],
                "dymap_results": []}

    def structure(self):
        '''Structure the workspace of this study
        and copy the necessary templates in the workspace'''
        if not os.path.isdir(self.paths["madx_in"]):
            os.mkdir(self.paths["madx_in"])
        if not os.path.isdir(self.paths["madx_out"]):
            os.mkdir(self.paths["madx_out"])
        if not os.path.isdir(self.paths["sixtrack_in"]):
            os.mkdir(self.paths["sixtrack_in"])
        if not os.path.isdir(self.paths["sixtrack_out"]):
            os.mkdir(self.paths["sixtrack_out"])

        tem_path = self.paths["templates"]
        if os.path.isdir(tem_path) and os.listdir(tem_path):
             for item in os.listdir(tem_path):
                 s = os.path.join(tem_path, item)
                 d = os.path.join(self.location, item)
                 if os.path.isfile(s):
                     shutil.copy2(s, d)
        else:
            print("Invalid templates folder!")


    def submit_mad6t(self, platform = 'local', **args):
        '''Submit the jobs to cluster or run locally'''
        clean = False
        if platform == 'local':
            if 'place' in args:
                execution_field = args['place']
            else:
                execution_field = 'temp'
            execution_field = os.path.abspath(execution_field)
            if not os.path.isdir(execution_field):
                os.makedirs(execution_field)
            if os.listdir(execution_field):
                clean = False
                print("Caution! The folder %s is not empty!"%execution_field)
            cur_path = os.getcwd()
            os.chdir(execution_field)
            if 'clean' in args:
                clean = args['clean']
            for i in self.mad6t_joblist:
                print("The job %s is running...."%i)
                mad6t_oneturn.run(i)
            print("All jobs are completed normally!")
            os.chdir(cur_path)
            if clean:
                shutil.rmtree(execution_field)
        elif platform.lower() == 'htcondor':
            #sys.path.append(app_path)
            pass
        else:
            print("Invlid platfrom!")

    def prepare_madx_single_input(self):
        '''Prepare the input files for madx and one turn sixtrack job'''
        self.config['madx'] = {}
        madx_sec = self.config['madx']
        madx_sec['source_path'] = self.paths['location']
        madx_sec['madx_exe'] = self.paths['madx_exe']
        madx_sec['mask_name'] = self.madx_input["mask_name"]
        status, out_files = utils.encode_strings(self.madx_output)
        if status:
            madx_sec['output_files'] = out_files
        else:
            print("Wrong setting of madx output files!")
            sys.exit(1)

        self.config['mask'] = {}
        mask_sec = self.config['mask']

        self.config['sixtrack'] = {}
        six_sec = self.config['sixtrack']
        six_sec['source_path'] = self.paths['location']
        six_sec['sixtrack_exe'] = self.paths['sixtrack_exe']
        status, temp = utils.encode_strings(self.oneturn_sixtrack_input['temp'])
        if status:
            six_sec['temp_files'] = temp
        else:
            print("Wrong setting of oneturn sixtrack templates!")
            sys.exit(1)
        status, in_files = utils.encode_strings(self.oneturn_sixtrack_input['input'])
        if status:
            six_sec['input_files'] = in_files
        else:
            print("Wrong setting of oneturn sixtrack input!")
            sys.exit(1)
        status, out_six = utils.encode_strings(self.oneturn_sixtrack_output)
        if status:
            six_sec['output_files'] = out_six
        else:
            print("Wrong setting of oneturn sixtrack outut!")
            sys.exit(1)
        self.config['fort3'] = self.oneturn_sixtrack_params

        keys = sorted(self.madx_params.keys())
        values = []
        for key in keys:
            values.append(self.madx_params[key])

        for element in itertools.product(*values):
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                mask_sec[ky] = str(vl)
            input_name = self.madx_name_conven('mad6t', keys, element, '.ini')
            prefix = self.madx_input['mask_name'].split('.')[0]
            madx_input_name = self.madx_name_conven(prefix, keys, element)
            madx_sec['input_name'] = madx_input_name
            out_name = self.madx_name_conven('Result', keys, element, '')
            mad6t_input = os.path.join(self.location, 'mad6t_input')
            madx_sec['dest_path'] = os.path.join(self.paths['madx_out'], out_name)
            six_sec['dest_path'] = os.path.join(self.paths['madx_out'], out_name)
            output = os.path.join(mad6t_input, input_name)
            with open(output, 'w') as f_out:
                self.config.write(f_out)
            self.mad6t_joblist.append(output)
            print('Successfully generate input file %s'%output)

    def madx_name_conven(self, prefix, keys, values, suffix = '.madx'):
        '''The convention for naming input file'''
        lStatus = True
        b = ''
        if len(keys) == len(values):
            a = ['_'.join(map(str, i)) for i in zip(keys, values)]
            b = '_'.join(map(str, a))
        else:
            print("The input list keys and values must have same length!")
            lStatus = False
        mk = prefix + '_' + b + suffix
        return mk

class StudyFactory(object):

    def __init__(self, workspace='./sandbox'):
        self.ws = os.path.abspath(workspace)
        self.studies = []
        self._setup_ws()

    def _setup_ws(self):
        '''Setup a workspace'''
        if not os.path.isdir(self.ws):
            os.mkdir(self.ws)
            print('Create new workspace %s!'%self.ws)
        else:
            print('The workspace %s already exists!'%self.ws)
        studies = os.path.join(self.ws, 'studies')
        if not os.path.isdir(studies):
            os.mkdir(studies)
        templates = os.path.join(self.ws, 'templates')
        if not os.path.isdir(templates):
            os.mkdir(templates)

        app_path = StudyFactory.app_path()
        tem_path = os.path.join(app_path, 'templates')
        contents = os.listdir(templates)
        if not contents:
            if os.path.isdir(tem_path) and os.listdir(tem_path):
                 for item in os.listdir(tem_path):
                     s = os.path.join(tem_path, item)
                     d = os.path.join(templates, item)
                     if os.path.isfile(s):
                         shutil.copy2(s, d)
            else:
                print("The templates folder %s is invlid!"%tem_path)

    def info(self):
        '''Print all the studies in the current workspace'''
        print(self.studies)
        return self.studies

    def new_study(self, name='', module_path=None, classname = 'MyStudy'):
        '''Create a new study'''
        studies = os.path.join(self.ws, 'studies')

        if len(name) == 0:
            i = len(self.studies)
            study_name = 'study_%03i'%(i)
        else:
            study_name = name
        study = os.path.join(studies, study_name)
        app_path = StudyFactory.app_path()
        config_temp = os.path.join(app_path, 'lib', 'config.py')

        if module_path is None:
            module_path = os.path.join(study, 'config.py')

        if not os.path.isdir(study):
            os.mkdir(study)
            shutil.copy2(config_temp, module_path)
            if os.path.isfile(module_path):
                self.studies.append(study)
                mod = SourceFileLoader(study_name, module_path).load_module()
                cls = getattr(mod, classname)
                print("Create new study %s"%study)
                return cls(name, study, self.ws)
            else:
                print("The configure file 'config.py' isn't found!")
                sys.exit(1)
        else:
            print("The study %s already exists, nothing to do!"%study)
            sys.exit(0)

    @staticmethod
    def app_path():
        '''Get the absolute path of the home directory of pysixdesk'''
        app_path = os.path.abspath(inspect.getfile(Study))
        app_path = os.path.dirname(os.path.dirname(app_path))
        return app_path

