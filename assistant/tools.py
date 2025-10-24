import copy

from assistant.functions import browse_web, search_google, get_weather

FUNCTION_MAPS = {
	'browse_web': browse_web,
	'search_google': search_google,
	'get_weather': get_weather,
}


def call_function(func_name, request, args):
	func = FUNCTION_MAPS.get(func_name)
	if not func:
		return False, '未发现函数{}'.format(func_name)

	arguments = copy.deepcopy(args)
	arguments['request'] = request
	ret, res = func(**arguments)
	return ret, res