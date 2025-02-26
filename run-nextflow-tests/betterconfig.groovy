import java.nio.file.Paths

import groovy.json.JsonSlurper
import groovy.json.JsonOutput
import groovy.lang.Closure
import groovy.lang.ProxyMetaClass
import groovy.util.ConfigObject

import nextflow.cli.CliOptions
import nextflow.cli.CmdRun
import nextflow.config.ConfigBuilder
import nextflow.plugin.Plugins
import nextflow.util.ConfigHelper

// Adapted from
// https://blog.mrhaki.com/2009/11/groovy-goodness-intercept-methods-with.html
class UserInterceptor implements Interceptor {
    // This class intercepts every method call on ConfigObjects. If the method
    // name is in the list of mocked methods, the original method is not called
    // and a static value is returned instead. This class cannot mock static
    // methods.

    boolean invokeMethod = true
    Map mocks
    Map dynamic_mocks = [:]

    UserInterceptor(String mock_file) {
        def jsonSlurper = new JsonSlurper()

        this.mocks = jsonSlurper.parse(new File(mock_file))
        assert this.mocks instanceof Map

        // Decode the "dynamic" mocks
        def dynamic_pattern = /^DYNAMIC\|(?<name>.*)/

        this.mocks.each { key, value ->
            def match = key =~ dynamic_pattern
            if (match) {
                assert value instanceof Map

                // Remove it from the plain mocks
                this.mocks.remove(key)
                this.dynamic_mocks[match.group("name")] = value
            }
        }
    }

    boolean doInvoke() {
        invokeMethod
    }

    Object beforeInvoke(Object obj, String name, Object[] args) {
        if (mocks.containsKey(name)) {
            invokeMethod = false
            return mocks[name]
        } else if (dynamic_mocks.containsKey(name)) {
            def args_str = JsonOutput.toJson(args)
            if (dynamic_mocks[name].containsKey(args_str)) {
                invokeMethod = false
                return dynamic_mocks[name][args_str]
            }
            throw new Exception("Dynamic mock $name does not contain $args_str")
        }
    }

    Object afterInvoke(Object obj, String name, Object[] args, Object result) {
        if (!invokeMethod) {
            invokeMethod = true
        }

        result
    }
}

class NeedsTaskException extends Exception {
    NeedsTaskException(String message) {
        super(message)
    }
}

// Adapted from
// https://blog.mrhaki.com/2009/11/groovy-goodness-intercept-methods-with.html
class TaskInterceptor implements Interceptor {
    // This class is specifically intended to mock closures with a string
    // representing their contents.
    boolean invokeMethod = true
    String current_process = null
    int current_attempt = 1
    boolean allow_getting_task = false
    boolean do_representation = false
    def represented_methods = ["check_limits", "retry_updater"]

    boolean doInvoke() {
        invokeMethod
    }

    Object beforeInvoke(Object obj, String name, Object[] args) {
        if (name == "get" && args[0] == "task") {
            if (!allow_getting_task) {
                throw new NeedsTaskException("Problem!")
            }

            obj.task.process = current_process
            obj.task.cpus = '$task.cpus'

            if (do_representation) {
                obj.task.attempt = '$task.attempt'
            } else {
                obj.task.attempt = current_attempt
            }
        }

        if (do_representation && represented_methods.contains(name) ) {
            invokeMethod = false
            return "$name(${args.join(', ')})"
        }
    }

    Object afterInvoke(Object obj, String name, Object[] args, Object result) {
        if (!invokeMethod) {
            invokeMethod = true
        }

        result
    }
}

void walk(interceptor, root, config_obj) {
    config_obj.each { key, value ->
        if (root == "process") {
            interceptor.current_process = key
        }

        if (value instanceof Closure) {
            try {
                try {
                    config_obj[key] = value.call()
                } catch (NeedsTaskException e) {
                    // Okay, see what resources it demands on the first three
                    // attempts
                    interceptor.allow_getting_task = true
                    config_obj[key] = [:]

                    // Add the representation value
                    interceptor.do_representation = true
                    try {
                        config_obj[key]['closure'] = value.call()
                    } catch (Exception) {
                        // This is probably an attempt to evaluate
                        // method(1 * task.attempt) - the argument is evaulated
                        // with a static method (java.lang.Integer.multiply),
                        // and I can't figure out a way around that
                        config_obj[key]['closure'] = "closure()"
                    }
                    interceptor.do_representation = false

                    // Add the results from attempts 1-3
                    interceptor.current_attempt = 1
                    config_obj[key][1] = value.call()
                    interceptor.current_attempt = 2
                    config_obj[key][2] = value.call()
                    interceptor.current_attempt = 3
                    config_obj[key][3] = value.call()

                    interceptor.allow_getting_task = false
                }
            } catch (Exception e) {
                System.out.println("Problem while expanding closure $root.$key")
                throw e
            }
        } else if (value instanceof ConfigObject) {
            walk(interceptor, "$root.$key", value)
        }

        if (root == "process") {
            interceptor.current_process = null
        }
    }
}

// This method is a mix of
// https://github.com/nextflow-io/nextflow/blob/7caffef977e0fa16177b0e7838e2b2b114c223b6/modules/nextflow/src/main/groovy/nextflow/cli/CmdConfig.groovy#L71-L114
// and
// https://github.com/nextflow-io/nextflow/blob/5e2ce9ed82ccbc70ec24a83e04f24b8d45855a78/modules/nextflow/src/main/groovy/nextflow/config/ConfigBuilder.groovy#L901-L906
void print_configuration() {
    // I don't know if this is necessary, but it seems harmless to leave in-place
    Plugins.init()

    // This is the equivalent of '-c <filename>'. The config file itself is
    // generated on-the-fly to mock out the System.* calls before including the
    // true config files.
    def launcher_options = new CliOptions()
    launcher_options.userConfig = [System.getenv("BL_CONFIG_FILE")]

    // This is the equivalent of '-params-file <filename>'
    def cmdRun = new CmdRun()
    cmdRun.paramsFile = System.getenv("BL_PARAMS_FILE")

    // This is the equivalent of '--param1=value1 --param2=value2'
    def jsonSlurper = new JsonSlurper()
    def cli_config = jsonSlurper.parse(new File(System.getenv("BL_CLI_PARAMS_FILE")))
    assert cli_config instanceof Map
    cli_config.each { key, value ->
        cmdRun.params."${key}" = value
    }

    def builder = new ConfigBuilder()
            .setShowClosures(false)
            .showMissingVariables(true)
            .setOptions(launcher_options)
            .setCmdRun(cmdRun)
            // Without this, both baseDir and projectDir would be incorrect
            .setBaseDir(Paths.get(System.getenv("BL_PIPELINE_DIR")))

    // Build the configuration with an interceptor to mock out user-defined
    // functions
    def proxy = ProxyMetaClass.getInstance(ConfigObject)
    proxy.interceptor = new UserInterceptor(System.getenv("BL_MOCKS_FILE"))

    def config

    proxy.use {
        config = builder.buildConfigObject()
    }

    // Attempt to expand all of the remaining closures under process with some
    // fancy mocking of `task`.
    def interceptor = new TaskInterceptor()
    proxy.interceptor = interceptor
    // Walk the config and resolve all of the closures
    proxy.use {
        walk(interceptor, "process", config.process)
    }

    def nextflowVersion = null

    try {
        // Try Nextflow 24+ (BuildInfo)
        def buildInfoClass = Class.forName('nextflow.BuildInfo')
        nextflowVersion = buildInfoClass.getDeclaredField('version').get(null)
    } catch (ClassNotFoundException | NoSuchFieldException e) {
        try {
            // Fallback to Nextflow 23 (Const)
            def constClass = Class.forName('nextflow.Const')
            nextflowVersion = constClass.getDeclaredField('APP_VER').get(null)
        } catch (Exception ignored) { }
    }

    System.out.println("betterconfig_nextflow_version=${nextflowVersion ?: 'unknown'}")

    System.out << ConfigHelper.toPropertiesString(config, false)
}

print_configuration()
