# test coverage.py
# Copyright 2004-2005, Ned Batchelder
# http://nedbatchelder.com/code/modules/coverage.html

showcompiler = 0
showparser = 0

from logilab.common.testlib import TestCase, unittest_main
import imp, os, random, sys, tempfile
from os.path import join
from cStringIO import StringIO
from shutil import rmtree

try:
    # development version
    from logilab.devtools.lib import coverage
except ImportError:
    # installed version
    import coverage

coverage_module = coverage 
coverage = coverage.Coverage()

try:
    from textwrap import dedent
except ImportError:
    # Copied from the textwrap module, for 2.2 testing.
    def dedent(text):
        """dedent(text : string) -> string
        """
        lines = text.expandtabs().split('\n')
        margin = None
        for line in lines:
            content = line.lstrip()
            if not content:
                continue
            indent = len(line) - len(content)
            if margin is None:
                margin = indent
            else:
                margin = min(margin, indent)
    
        if margin is not None and margin > 0:
            for i in range(len(lines)):
                lines[i] = lines[i][margin:]
    
        return '\n'.join(lines)
    
if hasattr(coverage, 'use_cache'):
    coverage.use_cache(0)

import compiler, compiler.visitor
import parser, symbol, token

class DebuggingAstVisitor(compiler.visitor.ASTVisitor):
    """ An ASTVisitor that helps me understand the ASTs returned by the
        compiler module.
    """
    def __init__(self):
        compiler.visitor.ASTVisitor.__init__(self)
        self.indent = 0
        
    def dispatch(self, node, *args):
        f = ''
        if hasattr(node, 'flags'):
            f = repr(node.flags)
        print "%s%s %s %s" % (' ' * self.indent, node.__class__.__name__,
            node.lineno, f)
        self.indent += 2
        compiler.visitor.ASTVisitor.dispatch(self, node, *args)
        self.indent -= 2

def annotateParseTree(tree):
    if type(tree) == type(()):
        t0 = tree[0]
        try:
            t0 = symbol.sym_name[t0]
        except KeyError:
            t0 = token.tok_name[t0]
        ret = [t0]
        for x in tree[1:]:
            ret.append(annotateParseTree(x))
        return ret
    else:
        return tree
        
class CoverageTest(TestCase):
    def setUp(self):
        # Create a temporary directory.
        self.noise = str(random.random())[2:]
        self.temproot = join(tempfile.gettempdir(),  'test_coverage'+self.noise)
        os.mkdir(self.temproot)
        self.tempdir = join(self.temproot, self.noise)
        os.mkdir(self.tempdir)
        self.olddir = os.getcwd()
        os.chdir(self.tempdir)
        # Keep a counter to make every call to checkCoverage unique.
        self.n = 0

        # Capture stdout, so we can use print statements in the tests and not
        # pollute the test output.
        self.oldstdout = sys.stdout
        self.capturedstdout = StringIO()
        sys.stdout = self.capturedstdout
        coverage.begin_recursive()
        
    def tearDown(self):
        coverage.end_recursive()
        sys.stdout = self.oldstdout
        # Get rid of the temporary directory.
        os.chdir(self.olddir)
        rmtree(self.temproot)

    def getStdout(self):
        return self.capturedstdout.getvalue()
    
    def makeFile(self, modname, text):
        """ Create a temp file with modname as the module name, and text as the
            contents.
        """
        text = dedent(text)
        if showcompiler:
            ast = compiler.parse(text+'\n\n')
            visitor = DebuggingAstVisitor()
            compiler.walk(ast, visitor, walker=visitor)

        if showparser:
            import parser, pprint
            tree = parser.suite(text+'\n').totuple(1)
            pprint.pprint(annotateParseTree(tree))
        
        # Create the python file.
        f = open(modname + '.py', 'w')
        f.write(text)
        f.close()

    def importModule(self, modname):
        """ Import the module named modname, and return the module object.
        """
        modfile = modname + '.py'
        f = open(modfile, 'r')
        
        for suff in imp.get_suffixes():
            if suff[0] == '.py':
                break
        try:
            mod = imp.load_module(modname, f, modfile, suff)
        finally:
            f.close()
        return mod
    
    def checkCoverage(self, text, lines, missing="", excludes=[], report=""):
            
        # We write the code into a file so that we can import it.
        # coverage.py wants to deal with things as modules with file names.
        # We append self.n because otherwise two calls in one test will use the
        # same filename and whether the test works or not depends on the
        # timestamps in the .pyc file, so it becomes random whether the second
        # call will use the compiled version of the first call's code or not!
        modname = 'coverage_test_' + self.noise + str(self.n)
        self.n += 1

        self.makeFile(modname, text)
        num_text = '\n'.join([': '.join(('#%i'%(i+1), line))
                            for i, line in enumerate(text.splitlines())])

        # Start up coverage.py
        coverage.erase()
        for exc in excludes:
            coverage.exclude(exc)
        coverage.start()
        self.assertEquals(self.nesting,1)

        # Import the python file, executing it.
        mod = self.importModule(modname)
        
        # Stop coverage.py
        coverage.stop()

        # Clean up our side effects
        del sys.modules[modname]

        # Get the analysis results, and check that they are right.
        _, clines, _, cmissing = coverage.analysis(mod)
        self.assertEqual(clines, lines, "statement mismatch:\nexpecting: %r'\
            '\nget:       %r\n===== in file =====\n%s\nusing: %s (%s)"
            % (lines, clines, num_text, coverage_module.__file__,
                coverage_module.__version__))
        self.assertEqual(cmissing, missing, "missing statement mismatch:\n"\
            "expecting: %r\nget:       %r\n===== in file ====\n%s\nusing: %s (%s)"
            % (missing, cmissing,num_text, coverage_module.__file__,
                coverage_module.__version__))

        if report:
            frep = StringIO()
            coverage.report(mod, file=frep)
            rep = " ".join(frep.getvalue().split("\n")[2].split()[1:])
            self.assertEqual(report, rep)

class BasicCoverageTests(CoverageTest):
    def testSimple(self):
        self.checkCoverage("""\
            a = 1
            b = 2
            
            c = 4
            # Nothing here
            d = 6
            """,
            [1,2,4,6], report="4 4 100% 0%")
        
    def testIndentationWackiness(self):
        # Partial final lines are OK.
        self.checkCoverage("""\
            if 0:
                pass
                """,
            [1,2], "2")

    def testMultilineInitializer(self):
        self.checkCoverage("""\
            d = {
                'foo': 1+2,
                'bar': (lambda x: x+1)(1),
                'baz': str(1),
            }

            e = { 'foo': 1, 'bar': 2 }
            """,
            [1,7], "")

    def testListComprehension(self):
        self.checkCoverage("""\
            l = [
                2*i for i in range(10)
                if i > 5
                ]
            assert l == [12, 14, 16, 18]
            """,
            [1,5], "")
        
class SimpleStatementTests(CoverageTest):
    def testExpression(self):
        self.checkCoverage("""\
            1 + 2
            1 + \\
                2
            """,
            [1,2], "")

    def testAssert(self):
        self.checkCoverage("""\
            assert (1 + 2)
            assert (1 + 
                2)
            assert (1 + 2), 'the universe is broken'
            assert (1 +
                2), \\
                'something is amiss'
            """,
            [1,2,4,5], "")

    def testAssignment(self):
        # Simple variable assignment
        self.checkCoverage("""\
            a = (1 + 2)
            b = (1 +
                2)
            c = \\
                1
            """,
            [1,2,4], "")

    def testAssignTuple(self):
        self.checkCoverage("""\
            a = 1
            a,b,c = 7,8,9
            assert a == 7 and b == 8 and c == 9
            """,
            [1,2,3], "")
            
    def testAttributeAssignment(self):
        # Attribute assignment
        self.checkCoverage("""\
            class obj: pass
            o = obj()
            o.foo = (1 + 2)
            o.foo = (1 +
                2)
            o.foo = \\
                1
            """,
            [1,2,3,4,6], "")
        
    def testListofAttributeAssignment(self):
        self.checkCoverage("""\
            class obj: pass
            o = obj()
            o.a, o.b = (1 + 2), 3
            o.a, o.b = (1 +
                2), (3 +
                4)
            o.a, o.b = \\
                1, \\
                2
            """,
            [1,2,3,4,7], "")
        
    def testAugmentedAssignment(self):
        self.checkCoverage("""\
            a = 1
            a += 1
            a += (1 +
                2)
            a += \\
                1
            """,
            [1,2,3,5], "")

    def testPass(self):
        self.checkCoverage("""\
            if 1==1:
                pass
            """,
            [1,2], "")
        
    def testDel(self):
        self.checkCoverage("""\
            d = { 'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1 }
            del d['a']
            del d[
                'b'
                ]
            del d['c'], \\
                d['d'], \\
                d['e']
            assert(len(d.keys()) == 0)
            """,
            [1,2,3,6,9], "")

    def testPrint(self):
        self.checkCoverage("""\
            print "hello, world!"
            print ("hey: %d" %
                17)
            print "goodbye"
            print "hello, world!",
            print ("hey: %d" %
                17),
            print "goodbye",
            """,
            [1,2,4,5,6,8], "")
        
    def testRaise(self):
        self.checkCoverage("""\
            try:
                raise Exception(
                    "hello %d" %
                    17)
            except:
                pass
            """,
            [1,2,6], "")

    def testReturn(self):
        self.checkCoverage("""\
            def fn():
                a = 1
                return a

            x = fn()
            assert(x == 1)
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            def fn():
                a = 1
                return (
                    a +
                    1)
                    
            x = fn()
            assert(x == 2)
            """,
            [1,2,3,7,8], "")
        self.checkCoverage("""\
            def fn():
                a = 1
                return (a,
                    a + 1,
                    a + 2)
                    
            x,y,z = fn()
            assert x == 1 and y == 2 and z == 3
            """,
            [1,2,3,7,8], "")

    def testYield(self):
        self.checkCoverage("""\
            from __future__ import generators
            def gen():
                yield 1
                yield (2+
                    3+
                    4)
                yield 1, \\
                    2
            a,b,c = gen()
            assert a == 1 and b == 9 and c == (1,2)
            """,
            [1,2,3,4,7,9,10], "")
        
    def testBreak(self):
        self.checkCoverage("""\
            for x in range(10):
                print "Hello"
                break
                print "Not here"
            """,
            [1,2,3,4], "4")
        
    def testContinue(self):
        self.checkCoverage("""\
            for x in range(10):
                print "Hello"
                continue
                print "Not here"
            """,
            [1,2,3,4], "4")
        
    def testImport(self):
        self.checkCoverage("""\
            import string
            from sys import path
            a = 1
            """,
            [1,2,3], "")
        self.checkCoverage("""\
            import string
            if 1 == 2:
                from sys import path
            a = 1
            """,
            [1,2,3,4], "3")
        self.checkCoverage("""\
            import string, \\
                os, \\
                re
            from sys import path, \\
                stdout
            a = 1
            """,
            [1,4,6], "")
        self.checkCoverage("""\
            import sys, sys as s
            assert s.path == sys.path
            """,
            [1,2], "")
        self.checkCoverage("""\
            import sys, \\
                sys as s
            assert s.path == sys.path
            """,
            [1,3], "")
        self.checkCoverage("""\
            from sys import path, \\
                path as p
            assert p == path
            """,
            [1,3], "")
        self.checkCoverage("""\
            from sys import \\
                *
            assert len(path) > 0
            """,
            [1,3], "")
        
    def testGlobal(self):
        self.checkCoverage("""\
            g = h = i = 1
            def fn():
                global g
                global h, \\
                    i
                g = h = i = 2
            fn()
            assert g == 2 and h == 2 and i == 2
            """,
            [1,2,6,7,8], "")
        self.checkCoverage("""\
            g = h = i = 1
            def fn():
                global g; g = 2
            fn()
            assert g == 2 and h == 1 and i == 1
            """,
            [1,2,3,4,5], "")

    def testExec(self):
        self.checkCoverage("""\
            a = b = c = 1
            exec "a = 2"
            exec ("b = " +
                "c = " +
                "2")
            assert a == 2 and b == 2 and c == 2
            """,
            [1,2,3,6], "")
        self.checkCoverage("""\
            vars = {'a': 1, 'b': 1, 'c': 1}
            exec "a = 2" in vars
            exec ("b = " +
                "c = " +
                "2") in vars
            assert vars['a'] == 2 and vars['b'] == 2 and vars['c'] == 2
            """,
            [1,2,3,6], "")
        self.checkCoverage("""\
            globs = {}
            locs = {'a': 1, 'b': 1, 'c': 1}
            exec "a = 2" in globs, locs
            exec ("b = " +
                "c = " +
                "2") in globs, locs
            assert locs['a'] == 2 and locs['b'] == 2 and locs['c'] == 2
            """,
            [1,2,3,4,7], "")
    def testNonregrIgnoreFunctionContent(self):
        self.checkCoverage("""\
            def uncalled():    #1
                a=12           #2
                b=13           #3
                assert False,"should not be executed" #4
                return 42      #5
                               #6 
            a=1                #7
            b=2                #8
            """,
            [1,2,3,4,5,7,8],"2-5"
            
            )
    def testNonregrIfFalseContent(self):
        self.checkCoverage("""\
            if False: #1
                a=12  #2
                b=13  #3
                assert False,"should not be executed" #4
            
            a=1 #6
            b=2 #7
            """,
            [1,2,3,4,6,7],"2-4"
            
            )

class CompoundStatementTests(CoverageTest):
    def testStatementList(self):
        self.checkCoverage("""\
            a = 1;
            b = 2; c = 3
            d = 4; e = 5;
            
            assert (a,b,c,d,e) == (1,2,3,4,5)
            """,
            [1,2,3,5], "")
        
    def testIf(self):
        self.checkCoverage("""\
            a = 1
            if a == 1:
                x = 3
            assert x == 3
            if (a == 
                1):
                x = 7
            assert x == 7
            """,
            [1,2,3,4,5,7,8], "")
        self.checkCoverage("""\
            a = 1
            if a == 1:
                x = 3
            else:
                y = 5
            assert x == 3
            """,
            [1,2,3,5,6], "5")
        self.checkCoverage("""\
            a = 1
            if a != 1:
                x = 3
            else:
                y = 5
            assert y == 5
            """,
            [1,2,3,5,6], "3")
        self.checkCoverage("""\
            a = 1; b = 2
            if a == 1:
                if b == 2:
                    x = 4
                else:
                    y = 6
            else:
                z = 8
            assert x == 4
            """,
            [1,2,3,4,6,8,9], "6-8")
    
    def testElif(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a == 1:
                x = 3
            elif b == 2:
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,3,4,5,7,8], "4-7", report="7 4 57% 100% 4-7")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1:
                x = 3
            elif b == 2:
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,3,4,5,7,8], "3, 7", report="7 5 71% 100% 3, 7")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1:
                x = 3
            elif b != 2:
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,3,4,5,7,8], "3, 5", report="7 5 71% 100% 3, 5")

    def testSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a == 1:
                x = 3
            elif \\
                b == 2:
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,4,6,7,9,10], "6-9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a != 1:
                x = 3
            elif \\
                b == 2:
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,4,6,7,9,10], "4, 9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a != 1:
                x = 3
            elif \\
                b != 2:
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,4,6,7,9,10], "4, 7")
        
    def testPathologicalSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a == 1
                ):
                x = 3
            elif (
                b == 2
                ):
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,5,6,9,11,12], "6-11")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a != 1
                ):
                x = 3
            elif (
                b == 2
                ):
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,5,6,9,11,12], "5, 11")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a != 1
                ):
                x = 3
            elif (
                b != 2
                ):
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,5,6,9,11,12], "5, 9")
        
    def testAbsurdSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a == 1 \\
                :
                x = 3
            elif b == 2 \\
                :
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,4,5,7,9,10], "5-9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1 \\
                :
                x = 3
            elif b == 2 \\
                :
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,4,5,7,9,10], "4, 9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1 \\
                :
                x = 3
            elif b != 2 \\
                :
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,4,5,7,9,10], "4, 7")

    def testWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,3,4,5], "")
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                break
                b = 99
            assert a == 3 and b == 1
            """,
            [1,2,3,4,5,6], "5")

    def testWhileElse(self):
        # Take the else branch.
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                a -= 1
            else:
                b = 99
            assert a == 0 and b == 99
            """,
            [1,2,3,4,6,7], "")
        # Don't take the else branch.
        self.checkCoverage("""\
            a = 3; b = 0             #1
            while a:                 #2
                b += 1               #3
                a -= 1               #4
                break                #5
                b = 123              #6
            else:                    #7
                b = 99               #8
            assert a == 2 and b == 1 #9
            """,
            [1,2,3,4,5,6,8,9], "6-8")
    
    def testSplitWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while \\
                a:
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,4,5,6], "")
        self.checkCoverage("""\
            a = 3; b = 0
            while (
                a
                ):
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,5,6,7], "")

    def testFor(self):
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:
                a += i
            assert a == 15
            """,
            [1,2,3,4], "")
        self.checkCoverage("""\
            a = 0
            for i in [1,
                2,3,4,
                5]:
                a += i
            assert a == 15
            """,
            [1,2,5,6], "")
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:
                a += i
                break
                a = 99
            assert a == 1
            """,
            [1,2,3,4,5,6], "5")
    
    def testForElse(self):
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
            else:
                a = 99
            assert a == 99
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
                break
                a = 99
            else:
                a = 123
            assert a == 1
            """,
            [1,2,3,4,5,7,8], "5-7")
    
    def testSplitFor(self):
        self.checkCoverage("""\
            a = 0
            for \\
                i in [1,2,3,4,5]:
                a += i
            assert a == 15
            """,
            [1,2,4,5], "")
        self.checkCoverage("""\
            a = 0
            for \\
                i in [1,
                2,3,4,
                5]:
                a += i
            assert a == 15
            """,
            [1,2,6,7], "")
    
    def testTryExcept(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:
                a = 99
            assert a == 1
            """,
            [1,2,3,5,6], "5")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            assert a == 99
            """,
            [1,2,3,4,6,7], "")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except ImportError:
                a = 99
            except:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,5,6,8,9], "6")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:
                a = 99
            else:
                a = 123
            assert a == 123
            """,
            [1,2,3,5,7,8], "5")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            else:
                a = 123
            assert a == 99
            """,
            [1,2,3,4,6,8,9], "8")
    
    def testTryFinally(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            finally:
                a = 99
            assert a == 99
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            a = 0; b = 0
            try:
                a = 1
                try:
                    raise Exception("foo")
                finally:
                    b = 123
            except:
                a = 99
            assert a == 99 and b == 123
            """,
            [1,2,3,4,5,7,9,10], "")

    def testFunctionDef(self):
        self.checkCoverage("""\
            a = 99
            def foo():
                ''' docstring
                '''
                return 1
                
            a = foo()
            assert a == 1
            """,
            [1,2,5,7,8], "")
        self.checkCoverage("""\
            def foo(
                a,
                b
                ):
                ''' docstring
                '''
                return a+b
                
            x = foo(17, 23)
            assert x == 40
            """,
            [1,7,9,10], "")
        self.checkCoverage("""\
            def foo(
                a = (lambda x: x*2)(10),
                b = (
                    lambda x:
                        x+1
                    )(1)
                ):
                ''' docstring
                '''
                return a+b
                
            x = foo()
            assert x == 22
            """,
            [1,10,12,13], "")

    def testClassDef(self):
        self.checkCoverage("""\
            # A comment.
            class theClass:
                ''' the docstring.
                    Don't be fooled.
                '''
                def __init__(self):
                    ''' Another docstring. '''
                    self.a = 1
                
                def foo(self):
                    return self.a
            
            x = theClass().foo()
            assert x == 1
            """,
            [2,6,8,10,11,13,14], "")    

class ExcludeTests(CoverageTest):
    def testSimple(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4   # -cc
            """,
            [1,3], "", ['-cc'])

    def testTwoExcludes(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if a == 99:
                a = 4   # -cc
                b = 5
                c = 6   # -xx
            assert a == 1 and b == 2
            """,
            [1,3,5,7], "5", ['-cc', '-xx'])
        
    def testExcludingIfSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4
                b = 5
                c = 6
            assert a == 1 and b == 2
            """,
            [1,7], "", ['if 0:'])

    def testExcludingIfButNotElseSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4
                b = 5
                c = 6
            else:
                a = 8
                b = 9
            assert a == 8 and b == 9
            """,
            [1,8,9,10], "", ['if 0:'])
        
    def testExcludingElseSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            else:          #pragma: NO COVER
                a = 8
                b = 9
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,10], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            
            # Lots of comments to confuse the else handler.
            # more.
            
            else:          #pragma: NO COVER

            # Comments here too.
            
                a = 8
                b = 9
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,17], "", ['#pragma: NO COVER'])

    def testExcludingElifSuites(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            elif 1==0:          #pragma: NO COVER
                a = 8
                b = 9
            else:          
                a = 11
                b = 12
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,11,12,13], "11-12", ['#pragma: NO COVER'])

    def testExcludingForSuite(self):
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:     #pragma: NO COVER
                a += i
            assert a == 15
            """,
            [1,4], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            for i in [1,
                2,3,4,
                5]:                #pragma: NO COVER
                a += i
            assert a == 15
            """,
            [1,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            for i in [1, 2, 3, 4, 5
                ]:                        #pragma: NO COVER
                a += i
                break
                a = 99
            assert a == 1
            """,
            [1,7], "", ['#pragma: NO COVER'])
            
    def testExcludingForElse(self):
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
                break
                a = 99
            else:               #pragma: NO COVER
                a = 123
            assert a == 1
            """,
            [1,2,3,4,5,8], "5", ['#pragma: NO COVER'])
    
    def testExcludingWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a*b:           #pragma: NO COVER
                b += 1
                break
                b = 99
            assert a == 3 and b == 0
            """,
            [1,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 3; b = 0
            while (
                a*b
                ):           #pragma: NO COVER
                b += 1
                break
                b = 99
            assert a == 3 and b == 0
            """,
            [1,8], "", ['#pragma: NO COVER'])

    def testExcludingWhileElse(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                break
                b = 99
            else:           #pragma: NO COVER
                b = 123
            assert a == 3 and b == 1
            """,
            [1,2,3,4,5,8], "5", ['#pragma: NO COVER'])

    def testExcludingTryExcept(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:           #pragma: NO COVER
                a = 99
            assert a == 1
            """,
            [1,2,3,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            assert a == 99
            """,
            [1,2,3,4,6,7], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except ImportError:    #pragma: NO COVER
                a = 99
            except:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,8,9], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:       #pragma: NO COVER
                a = 99
            else:
                a = 123
            assert a == 123
            """,
            [1,2,3,7,8], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            else:              #pragma: NO COVER
                a = 123
            assert a == 99
            """,
            [1,2,3,4,6,9], "", ['#pragma: NO COVER'])
    
    def testExcludingFunction(self):
        self.checkCoverage("""\
            def fn(foo):      #pragma: NO COVER
                a = 1
                b = 2
                c = 3
                
            x = 1
            assert x == 1
            """,
            [6,7], "", ['#pragma: NO COVER'])

    def testExcludingMethod(self):
        self.checkCoverage("""\
            class Fooey:
                def __init__(self):
                    self.a = 1
                    
                def foo(self):     #pragma: NO COVER
                    return self.a
                    
            x = Fooey()
            assert x.a == 1
            """,
            [1,2,3,8,9], "", ['#pragma: NO COVER'])
        
    def testExcludingClass(self):
        self.checkCoverage("""\
            class Fooey:            #pragma: NO COVER
                def __init__(self):
                    self.a = 1
                    
                def foo(self):
                    return self.a
                    
            x = 1
            assert x == 1
            """,
            [8,9], "", ['#pragma: NO COVER'])

if sys.hexversion >= 0x020400f0 and 0:    # Don't test this yet.
    class Py24Tests(CoverageTest):
        def testFunctionDecorators(self):
            self.checkCoverage("""\
                def require_int(func):
                    def wrapper(arg):
                        assert isinstance(arg, int)
                        return func(arg)
                
                    return wrapper
                
                @require_int
                def p1(arg):
                    return arg*2
                
                assert p1(10) == 20
                """,
                [1,2,3,4,6,8,9,10,12], "")
        
if sys.hexversion >= 0x020300f0:
    # threading support was new in 2.3, only test there.
    class ThreadingTests(CoverageTest):
        def testThreading(self):
            self.checkCoverage("""\
                import threading
    
                def fromMainThread():
                    return "called from main thread"
                
                def fromOtherThread():
                    return "called from other thread"
                
                def neverCalled():
                    return "no one calls me"
                
                t = threading.Thread(target=fromOtherThread)
                t.start()
                fromMainThread()
                t.join()
                """,
                [1,3,4,6,7,9,10,12,13,14,15], "10")
class SetTraceTests(CoverageTest):
    
    def setUp(self):
        # Start up coverage.py
        coverage.erase()
        CoverageTest.setUp(self)
        try:
            set()
        except NameError:
            from sets import Set as set
        
        self.log = set()
        self.expected_log = set()
        self.log_counter = 0
    def tearDown(self):
        coverage.stop()
        sys.settrace(None)

    def make_tracer(self,log_value=0):
        def tracer(a,b,c,log=self.log,log_value=log_value):
            log.add(log_value)
        return tracer
    def set_tracer_log(self,value=0):
        sys.settrace(self.make_tracer(value))

    def assertLog(self):
        self._assertEitherLogOrNoLog(True)
    def assertNoLog(self):
        self._assertEitherLogOrNoLog(False)
    def _assertEitherLogOrNoLog(self,log):
        self.set_tracer_log(self.log_counter)
        if log:
            self.expected_log.add(self.log_counter)
        self.log_counter+=1
        self.assertEqual(self.log,self.expected_log)


    def testSimpleCall(self):
        import sys
        
        coverage.start()

        self.assertNoLog()

        coverage.stop()

        self.assertLog()
    
    def testMultipleSimpleCall(self):
        import sys
        
        coverage.start()

        self.assertNoLog()

        coverage.stop()

        self.assertLog()
        
        coverage.start()

        self.assertNoLog()

        coverage.stop()
        
        self.assertLog()
    
    def testNestedCall(self):
        import sys
        
        coverage.start()
        #
        self.assertNoLog()
        #
        coverage.start()
        ##
        self.assertNoLog()
        ##
        coverage.stop()
        #
        self.assertNoLog()
        #
        coverage.stop()
        
        self.assertLog()
    
    def testMultipleNestedCall(self):
        import sys
        
        coverage.start()
        #
        self.assertNoLog()
        #
        coverage.start()
        ##
        self.assertNoLog()
        ##
        coverage.stop()
        #
        self.assertNoLog()
        #
        coverage.start()
        ##
        self.assertNoLog()
        ##
        coverage.stop()
        #
        self.assertNoLog()
        #
        coverage.stop()
        
        self.assertLog()


class ApiTests(CoverageTest):
    def testSimple(self):
        coverage.erase()

        self.makeFile("mycode", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
            d = 5
            """)
            
        # Import the python file, executing it.
        coverage.start()
        self.importModule("mycode")
        coverage.stop()
    
        filename, statements, missing, readablemissing = coverage.analysis(
            "mycode.py")
        self.assertEqual(statements, [1,2,3,4,5])
        self.assertEqual(missing, [4])
        self.assertEqual(readablemissing, "4")
        
    def doReportWork(self, modname):
        coverage.erase()

        self.makeFile(modname, """\
            a = 1
            b = 2
            if b == 3:
                c = 4
                d = 5
                e = 6
            f = 7
            """)
            
        # Import the python file, executing it.
        coverage.start()
        self.importModule(modname)
        coverage.stop()
        coverage.analysis(modname + ".py")
        
    def testReport(self):
        self.doReportWork("mycode2")
        coverage.report(["mycode2.py"])
        self.assertTextEqual(self.getStdout(), dedent("""\
            Name      Stmts   Exec  Cover %Missing   Missing
            ------------------------------------------------
            mycode2       7      4    57%   100%   4-6
            """))

    def testReportFile(self):
        self.doReportWork("mycode3")
        fout = StringIO()
        coverage.report(["mycode3.py"], file=fout)
        self.assertTextEqual(self.getStdout(), "")
        self.assertTextEqual(fout.getvalue(), dedent("""\
            Name      Stmts   Exec  Cover %Missing   Missing
            ------------------------------------------------
            mycode3       7      4    57%   100%   4-6
            """))

#cst = CompoundStatementTests
#sst = SimpleStatementTests

if __name__ == '__main__':
    print "Testing under Python version:\n", sys.version
    coverage
    unittest_main()
    coverage

# TODO: split "and" conditions across lines, and detect not running lines.
#         (Can't be done: trace function doesn't get called for each line
#         in an expression!)
# TODO: Generator comprehensions? Decorators?
# TODO: Constant if tests ("if 1:").  Py 2.4 doesn't execute them.

# $Id: test_coverage.py,v 1.1 2005-12-29 14:28:12 syt Exp $
