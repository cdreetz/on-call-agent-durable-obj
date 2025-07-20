from workers import DurableObject, Response, handler
import random

"""
 * Welcome to Cloudflare Workers! This is your first Durable Objects application.
 *
 * - Run `npm run dev` in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your Durable Object in action
 * - Run `npm run deploy` to publish your application
 *
 * Learn more at https://developers.cloudflare.com/durable-objects
"""

"""
 * Env provides a mechanism to reference bindings declared in wrangler.jsonc within Python
 *
 * @typedef {Object} Env
 * @property {DurableObjectNamespace} MY_DURABLE_OBJECT - The Durable Object namespace binding
"""

# A Durable Object's behavior is defined in an exported Python class
class MyDurableObject(DurableObject):
    """
     * The constructor is invoked once upon creation of the Durable Object, i.e. the first call to
     * `DurableObjectStub::get` for a given identifier (no-op constructors can be omitted)
     *
     * @param {DurableObjectState} ctx - The interface for interacting with Durable Object state
     * @param {Env} env - The interface to reference bindings declared in wrangler.jsonc
    """
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self._init_db()

    def _init_db(self):
        self.ctx.storage.sql.exec("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value TEXT
            )
        """)

    """
     * The Durable Object exposes an RPC method `say_hello` which will be invoked when when a Durable
     *  Object instance receives a request from a Worker via the same method invocation on the stub
     *
     * @param {string} name - The name provided to a Durable Object instance from a Worker
     * @returns {Promise<string>} The greeting to be sent back to the Worker
    """
    async def say_hello(self, name):
        return f"Hello, {name}!"

    async def give_random(self):
        return f"So random.. {random.random()}"
    


"""
* This is the standard fetch handler for a Cloudflare Worker
*
* @param {Request} request - The request submitted to the Worker from the client
* @param {Env} env - The interface to reference bindings declared in wrangler.jsonc
* @param {ExecutionContext} ctx - The execution context of the Worker
* @returns {Promise<Response>} The response to be sent back to the client
"""
@handler
async def on_fetch(request, env, ctx):
    # Create a `DurableObjectId` for an instance of the `MyDurableObject`
    # class named "foo". Requests from all Workers to the instance named
    # "foo" will go to a single globally unique Durable Object instance.
    id = env.MY_DURABLE_OBJECT.idFromName("foo")

    # Create a stub to open a communication channel with the Durable
    # Object instance.
    stub = env.MY_DURABLE_OBJECT.get(id)

    # Call the `say_hello()` RPC method on the stub to invoke the method on
    # the remote Durable Object instance
    #res = await stub.say_hello("world")
    from urllib.parse import urlparse, parse_qs
    url = urlparse(request.url)
    params = parse_qs(url.query)

    fun = params.get('fun', [''])[0]
    body = params.get('body', [''])[0]

    if fun == "say_hello":
        res = await stub.say_hello(body)
    elif fun == "give_random":
        res = await stub.give_random()
    else:
        res = "Dunno what u want me to do"

    return Response(res)

