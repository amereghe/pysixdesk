import os
import sys
import time
import copy
import shutil
import inspect
import itertools
import configparser
import collections
import importlib
import utils
import mad6t_oneturn
import sixtrack

from importlib.machinery import SourceFileLoader
from pysixdb import SixDB

class Study(object):

    def __init__(self, name='example_study', loc=os.getcwd()):
        '''Constructor'''
        self.name = name
        self.location = os.path.abspath(loc)
        self.study_path = os.path.join(self.location, self.name)
        self.config = configparser.ConfigParser()
        self.config.optionxform = str #preserve case
        self.mad6t_joblist = []
        self.sixtrack_joblist = []
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
        self.boinc_vars = collections.OrderedDict()
        #initialize default values
        Study._defaults(self)

    def _defaults(self):
        '''initialize a study with some default settings'''
        #full path to madx
        self.paths["madx_exe"] = "/afs/cern.ch/user/m/mad/bin/madx"
        #full path to sixtrack
        self.paths["sixtrack_exe"] = "/afs/cern.ch/project/sixtrack/build/sixtrack"
        self.paths["study_path"] = self.study_path
        self.paths["madx_in"] = os.path.join(self.study_path, "mad6t_input")
        self.paths["madx_out"] = os.path.join(self.study_path, "mad6t_output")
        self.paths["sixtrack_in"] = os.path.join(self.study_path, "sixtrack_input")
        self.paths["sixtrack_out"] = os.path.join(self.study_path, "sixtrack_output")
        self.paths["templates"] = self.study_path
        self.paths["boinc_spool"] = "/afs/cern.ch/work/b/boinc/boinc"

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
        self.oneturn_sixtrack_input['input'] = copy.deepcopy(self.madx_output)
        self.oneturn_sixtrack_output = ['fort.10']
        self.sixtrack_output = ['fort.10']

        #Default definition of the database tables
        self.tables['mad6t_task'] = {
                'job_name': 'text',
                'input_file': 'blob',
                'task_status': 'text',
                'job_id': 'int',
                'mtime': 'float'}
        self.tables['mad6t_job'] = {
                'task_id': 'int',
                'madx_in' : 'blob',
                'madx_stdout': 'blob',
                'job_stdout': 'blob',
                'job_stderr': 'blob',
                'job_stdlog': 'blob',
                'count': 'int',
                'status': 'text',
                'mtime': 'float'}
        self.tables['sixtrack_task']={
                'mad6t_id': 'int',
                'task_status': 'text',
                'job_id': 'int',
                'mtime': 'float'}
        self.tables['sixtrack_job'] = {
                'task_id': 'int',
                'job_stdout': 'blob',
                'job_stderr': 'blob',
                'job_stdlog': 'blob',
                'count': 'int',
                'status': 'text',
                'mtime': 'float'}
        self.tables['result'] = {
                'betax': 'float',
                'betay': 'float'}#TODO

        self.boinc_vars['workunitName'] = 'sixdesk'
        self.boinc_vars['fpopsEstimate'] = 30*2*10e5/2*10e6*6
        self.boinc_vars['fpopsBound'] = self.boinc_vars['fpopsEstimate']*1000
        self.boinc_vars['memBound'] = 100000000
        self.boinc_vars['diskBound'] = 200000000
        self.boinc_vars['delayBound'] = 2400000
        self.boinc_vars['redundancy'] = 2
        self.boinc_vars['copies'] = 2
        self.boinc_vars['errors'] = 5
        self.boinc_vars['numIssues'] = 5
        self.boinc_vars['resultsWithoutConcensus'] = 3
        self.boinc_vars['appName'] = 'sixtrack'

    def update_tables(self):
        '''Update the database tables after the user define the scan parameters
        and the output files. This method should be called before 'structure()'
        '''
        for key in self.madx_params.keys():
            self.tables['mad6t_task'][key] = 'INT'
        for key in self.madx_output.values():
            self.tables['mad6t_task'][key] = 'BLOB'

        for key in self.sixtrack_params.keys():
            self.tables['sixtrack_task'][key] = 'INT'
        for key in self.sixtrack_output:
            self.tables['sixtrack_task'][key] = 'BLOB'

    def structure(self):
        '''Structure the workspace of this study.
        Prepare the input and output folders.
        Copy the required template files.
        Initialize the database with the defined tables.'''

        temp = self.paths["templates"]
        if not os.path.isdir(temp) or not os.listdir(temp):
            if not os.path.exists(temp):
                os.makedirs(temp)
            app_path = StudyFactory.app_path()
            tem_path = os.path.join(app_path, 'templates')
            print(tem_path)
            if os.path.isdir(tem_path) and os.listdir(tem_path):
                for item in os.listdir(tem_path):
                    s = os.path.join(tem_path, item)
                    d = os.path.join(temp, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)
                print("Copy templates from default source templates folder!")
            else:
                print("The default source templates folder %s is inavlid!"%tem_path)
                sys.exit(1)

        if not os.path.isdir(self.paths["madx_in"]):
            os.makedirs(self.paths["madx_in"])
        if not os.path.isdir(self.paths["madx_out"]):
            os.makedirs(self.paths["madx_out"])
        if not os.path.isdir(self.paths["sixtrack_in"]):
            os.makedirs(self.paths["sixtrack_in"])
        if not os.path.isdir(self.paths["sixtrack_out"]):
            os.makedirs(self.paths["sixtrack_out"])

        #Initialize the database
        dbname = os.path.join(self.study_path, 'data.db')
        self.db = SixDB(dbname, True)
        self.db.create_tables(self.tables)

        cont = os.listdir(temp)
        require = self.oneturn_sixtrack_input["temp"]
        require.append(self.madx_input["mask_name"])
        for re in require:
            if re not in cont:
                print("The required file %s isn't found in %s!"%(re, temp))
                sys.exit(1)
        print("All required files are ready!")

    def submit_sixtrack(self, **args):
        '''Sumbit the sixtrack jobs to htctondor. p.s. Now we test locally'''
        if 'place' in args:
            execution_field = args['place']
        else:
            execution_field = 'temp'
        execution_field = os.path.abspath(execution_field)
        if not os.path.isdir(execution_field):
            os.makedirs(execution_field)
        if os.listdir(execution_field):
            print("Caution! The folder %s is not empty!"%execution_field)
        cur_path = os.getcwd()
        os.chdir(execution_field)
        for i in self.sixtrack_joblist:
            print("The sixtrack job %s is running...."%i)
            sixtrack.run(i)
            print(i)
        print("All sxitrack jobs are completed normally!")
        os.chdir(cur_path)

    def prepare_sixtrack_input(self, server='htcondor'):
        '''Prepare the input files for sixtrack job'''
        self.config.clear()
        self.config['sixtrack'] = {}
        six_sec = self.config['sixtrack']
        six_sec['source_path'] = self.paths['templates']
        six_sec['sixtrack_exe'] = self.paths['sixtrack_exe']
        inp = self.sixtrack_input['input']
        six_sec['input_files']= self.utils_eval(utils.encode_strings, [inp])
        six_sec['boinc_dir'] = self.paths['boinc_spool']
        if server.lower() == 'htcondor':
            six_sec['boinc'] = 'false'
        elif server.lower() == 'boinc':
            six_sec['boinc'] = 'true'
        else:
            print("Unsupported platform!")
            sys.exit(1)
        status, temp = utils.encode_strings(self.sixtrack_input['temp'])
        if status:
            six_sec['temp_files'] = temp
        else:
            print("Wrong setting of sixtrack templates!")
            sys.exit(1)
        status, out_six = utils.encode_strings(self.sixtrack_output)
        if status:
            six_sec['output_files'] = out_six
        else:
            print("Wrong setting of oneturn sixtrack outut!")
            sys.exit(1)

        #self.config['fort3'] = self.sixtrack_params
        self.config['fort3'] = {}
        fort3_sec = self.config['fort3']
        keys = sorted(self.madx_params.keys())
        madx_vals = self.db.select('mad6t_task', keys, where="task_status='complete'")
        for element in madx_vals:
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                fort3_sec[ky] = str(vl)
        madx_jobnames = self.db.select('mad6t_task', ['job_name'], where="task_status='complete'")
        cols = list(self.sixtrack_input['input'].values())
        task_table = {}
        for item in madx_jobnames:
            item = item[0]
            item_path = os.path.join(self.paths['sixtrack_in'], item)
            if not os.path.isdir(item_path):
                os.makedirs(item_path)
            s_keys = sorted(self.sixtrack_params.keys())
            values = []
            keys = []
            for key in s_keys:
                val = self.sixtrack_params[key]
                if isinstance(val, list):
                    keys.append(key)
                    s_keys.remove(key)
                    values.append(val)
                else:
                    fort3_sec[key] = str(val)
            for element in itertools.product(*values):
                for i in range(len(element)):
                    ky = keys[i]
                    vl = element[i]
                    fort3_sec[ky] = str(vl)
                job_name = self.madx_name_conven('', keys, element, '')
                input_path = os.path.join(item_path, job_name)
                dest_path = os.path.join(self.paths['sixtrack_out'], item, job_name)
                if not os.path.isdir(input_path):
                    os.makedirs(input_path)
                six_sec['input_path'] = input_path
                six_sec['dest_path'] = dest_path
                where = "job_name='%s'"%(item)
                madx_outs = self.db.select('mad6t_task', cols, where)
                num = len(cols)
                for i in range(num):
                    out = madx_outs[0][i]
                    filename = os.path.join(input_path, cols[i])
                    status = utils.decompress_buf(out, filename)
                self.config['boinc'] = self.boinc_vars
                input_name = 'test.ini'
                output = os.path.join(input_path, input_name)
                with open(output, 'w') as f_out:
                    self.config.write(f_out)
                self.sixtrack_joblist.append(output)
                print('Successfully generate input file %s'%output)

    def submit_mad6t(self, platform='local', **args):
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
                i = os.path.join(self.paths['madx_in'], i+'.ini')
                print("The job %s is running...."%i)
                run_status = mad6t_oneturn.run(i)#run the job
            print("All jobs are completed normally!")
            os.chdir(cur_path)
            if clean:
                shutil.rmtree(execution_field)
        elif platform.lower() == 'htcondor':
            #sys.path.append(app_path)
            pass
        else:
            print("Invlid platfrom!")

    def collect_mad6t_results(self):
        '''Collect the results of madx and oneturn sixtrack job and store in
        database
        '''
        mad6t_path = self.paths['madx_out']
        if os.path.isdir(mad6t_path) and os.listdir(mad6t_path):
            for item in os.listdir(mad6t_path):
                job_path = os.path.join(mad6t_path, item)
                if os.path.isdir(job_path) and os.listdir(job_path):
                    job_table = {}
                    task_table = {}
                    contents = os.listdir(job_path)
                    madx_in = [s for s in contents if item in s]
                    job_table['status'] = 'Success'
                    if madx_in:
                        madx_in = os.path.join(job_path, madx_in[0])
                        job_table['madx_in'] = self.utils_eval(utils.compress_buf,\
                                [madx_in,'gzip'])
                    else:
                        print("The madx_in file for job %s dosen't exist! The job failed!"%item)
                        job_table['status'] = 'Failed'
                    madx_out = [s for s in contents if 'madx_stdout' in s]
                    if madx_out:
                        madx_out = os.path.join(job_path, madx_out[0])
                        job_table['madx_stdout'] = self.utils_eval(utils.compress_buf,\
                                [madx_out,'gzip'])
                    else:
                        print("The madx_out file for job %s doesn't exist! The job failed!"%item)
                        job_table['status'] = 'Failed'
                    for out in self.madx_output.values():
                        out_f = [s for s in contents if out in s]
                        if out_f:
                            out_f = os.path.join(job_path, out_f[0])
                            task_table[out] = self.utils_eval(utils.compress_buf,\
                                    [out_f,'gzip'])
                        else:
                            job_table['status'] = 'Failed'
                            print("The madx output file %s for job %s doesn't exist! The job failed!"%(out, item))

                    task_id = self.mad6t_joblist.index(item) + 1
                    job_table['task_id'] = task_id
                    job_table['mtime'] = time.time()
                    self.db.insert('mad6t_job', job_table)
                    if job_table['status'] is 'Success':
                        where = 'rowid = %i'%task_id
                        task_table['task_status'] = 'complete'
                        self.db.update('mad6t_task', task_table, where)
                else:
                    print("The job path %s is invalid!"%item)
        else:
            print("The result path %s is invalid!"%mad6t_path)

    def prepare_madx_single_input(self):
        '''Prepare the input files for madx and one turn sixtrack job'''
        self.config.clear()
        self.config['madx'] = {}
        madx_sec = self.config['madx']
        madx_sec['source_path'] = self.paths['templates']
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
        six_sec['source_path'] = self.paths['templates']
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
            madx_table = {}
            for i in range(len(element)):
                ky = keys[i]
                vl = element[i]
                mask_sec[ky] = str(vl)
                madx_table[ky] = vl
            prefix = self.madx_input['mask_name'].split('.')[0]
            job_name = self.madx_name_conven(prefix, keys, element, '')
            check_jobs = self.db.select('mad6t_task', ['job_name','task_status'])
            if check_jobs:
                checks = list(zip(*check_jobs))
                if job_name in checks[0]:
                    i = checks[0].index(job_name)
                    if checks[1][i] == 'complete':
                        self.mad6t_joblist.append(job_name)
                        print("The job %s has already completed normally!"%job_name)
                        continue
            input_name = job_name + '.ini'
            madx_input_name = self.madx_name_conven(prefix, keys, element)
            madx_sec['input_name'] = madx_input_name
            mad6t_input = self.paths['madx_in']
            madx_sec['dest_path'] = os.path.join(self.paths['madx_out'], job_name)
            six_sec['dest_path'] = os.path.join(self.paths['madx_out'], job_name)
            output = os.path.join(mad6t_input, input_name)
            with open(output, 'w') as f_out:
                self.config.write(f_out)
            madx_table['task_status'] = 'incomplete'
            madx_table['job_name'] = job_name
            madx_table['mtime'] = time.time()
            status, buf = utils.compress_buf(output)
            if status:
                madx_table['input_file'] = buf
            else:
                sys.exit(1)
            self.db.insert('mad6t_task', madx_table)
            print('Successfully generate input file %s'%output)
            self.mad6t_joblist.append(job_name)
            print('Store the input information into database!')

    def transfer_data(self):
        '''Transfer the result to database'''
        result_path = self.study_path
        tables = self.tables
        self.db.transfer_madx_oneturn_res(result_path, tables)

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

    def utils_eval(self, fun, inputs, action=sys.exit):
        '''Evaluate the specified function'''
        output = None
        status, output = fun(*inputs)
        if status:
            return output
        else:
            action()


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
        else:
            self._load()
            self.info()
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
                print("The templates folder %s is invalid!"%tem_path)

    def _load(self):
        '''Load the information from an exist workspace!'''
        studies = os.path.join(self.ws, 'studies')
        for item in os.listdir(studies):
            if os.path.isdir(item):
                self.studies.append(item)

    def info(self):
        '''Print all the studies in the current workspace'''
        print(self.studies)
        return self.studies

    def prepare_study(self, name = ''):
        '''Prepare the config and temp files for a study'''
        studies = os.path.join(self.ws, 'studies')
        if len(name) == 0:
            i = len(self.studies)
            study_name = 'study_%03i'%(i)
        else:
            study_name = name

        study = os.path.join(studies, study_name)
        app_path = StudyFactory.app_path()
        config_temp = os.path.join(app_path, 'lib', 'config.py')
        if not os.path.isdir(study):
            os.makedirs(study)

        tem_path = os.path.join(self.ws, 'templates')
        if os.path.isdir(tem_path) and os.listdir(tem_path):
             for item in os.listdir(tem_path):
                 s = os.path.join(tem_path, item)
                 d = os.path.join(study, item)
                 if os.path.isfile(s):
                     shutil.copy2(s, d)
        else:
            print("Invalid templates folder!")
            sys.exit(1)

    def new_study(self, name, module_path=None, classname='MyStudy'):
        '''Create a new study with a prepared study path'''
        loc = os.path.join(self.ws, 'studies')
        study = os.path.join(loc, name)
        if os.path.isdir(study):
            if module_path is None:
                module_path = os.path.join(study, 'config.py')

            if os.path.isfile(module_path):
                self.studies.append(study)
                module_name = os.path.abspath(module_path)
                module_name = module_name.replace('.py', '')
                mod = SourceFileLoader(module_name, module_path).load_module()
                cls = getattr(mod, classname)
                print("Create a study instance %s"%study)
                return cls(name, loc)
            else:
                print("The configure file 'config.py' isn't found!")
                sys.exit(1)
        else:
            print("Invalid study path! The study path should be initialized at first!")

    @staticmethod
    def app_path():
        '''Get the absolute path of the home directory of pysixdesk'''
        app_path = os.path.abspath(inspect.getfile(Study))
        app_path = os.path.dirname(os.path.dirname(app_path))
        return app_path

