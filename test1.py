
result_path = "result.txt"
f_result = open(result_path, "a")
ls = [1, 2, 1, 1, 2, 1, 2]
a = ls.count(1)
f_result.write(str(ls))
f_result.write("\n")
f_result.write("count 1 = %s"%str(a))
f_result.close()